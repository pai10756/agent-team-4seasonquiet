#!/usr/bin/env python3
"""
Create a VibeVoice Realtime voice preset (.pt) from a reference audio file.
This runs the model's prefill phase on the voice prompt to create a cached KV state.
"""
import argparse
import math
import os
import copy
import torch
import numpy as np
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Create voice preset from audio")
    parser.add_argument("--audio_path", type=str, required=True, help="Path to reference audio (wav/mp3)")
    parser.add_argument("--model_path", type=str, default="microsoft/VibeVoice-Realtime-0.5B")
    parser.add_argument("--output_path", type=str, required=True, help="Output .pt file path")
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    print(f"Loading processor from {args.model_path}")
    from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
    from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference

    processor = VibeVoiceStreamingProcessor.from_pretrained(args.model_path)
    tokenizer = processor.tokenizer

    print(f"Loading model from {args.model_path}")
    if args.device == "cuda":
        load_dtype = torch.bfloat16
        try:
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                args.model_path, torch_dtype=load_dtype, device_map="cuda",
                attn_implementation="flash_attention_2",
            )
        except Exception:
            print("flash_attention_2 not available, using sdpa")
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                args.model_path, torch_dtype=load_dtype, device_map="cuda",
                attn_implementation="sdpa",
            )
    else:
        load_dtype = torch.float32
        model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
            args.model_path, torch_dtype=load_dtype, device_map=args.device,
            attn_implementation="sdpa",
        )
    model.eval()

    # Load and process audio
    print(f"Loading audio from {args.audio_path}")
    audio_wav = processor.audio_processor._load_audio_from_path(args.audio_path)
    if processor.db_normalize and processor.audio_normalizer:
        audio_wav = processor.audio_normalizer(audio_wav)

    audio_duration = len(audio_wav) / 24000
    print(f"Audio duration: {audio_duration:.1f}s, samples: {len(audio_wav)}")

    # Build the voice prompt token sequence
    # Format: system_prompt + " Voice input:\n Speaker 0:" + <speech_start> + [vae_tokens] + <speech_end> + "\n Speech output:\n" + <speech_start>
    vae_token_id = tokenizer.speech_diffusion_id
    vae_tok_len = math.ceil(len(audio_wav) / processor.speech_tok_compress_ratio)
    print(f"VAE token length: {vae_tok_len}")

    # Build system prompt (same as the model's default)
    system_prompt = "You are a helpful voice assistant. Repeat the text exactly as given, with natural and expressive speech."
    system_tokens = tokenizer.encode(system_prompt)

    # Voice input section
    voice_prefix = tokenizer.encode(" Voice input:\n Speaker 0:", add_special_tokens=False)
    voice_tokens = (
        voice_prefix
        + [tokenizer.speech_start_id]
        + [vae_token_id] * vae_tok_len
        + [tokenizer.speech_end_id]
    )
    voice_speech_mask = (
        [False] * len(voice_prefix)
        + [False]  # speech_start
        + [True] * vae_tok_len  # actual speech
        + [False]  # speech_end
    )

    # Text output section header
    text_output_prefix = tokenizer.encode("\n Speech output:\n", add_special_tokens=False)
    speech_start_token = [tokenizer.speech_start_id]

    # Full LM input
    lm_input_ids = system_tokens + voice_tokens + text_output_prefix + speech_start_token
    lm_speech_input_mask = (
        [False] * len(system_tokens)
        + voice_speech_mask
        + [False] * len(text_output_prefix)
        + [False]  # speech_start
    )

    # TTS LM input is same as LM input for prefill
    tts_lm_input_ids = list(lm_input_ids)
    tts_lm_speech_input_mask = list(lm_speech_input_mask)

    print(f"LM input length: {len(lm_input_ids)}, TTS LM input length: {len(tts_lm_input_ids)}")

    # Prepare speech tensors
    speech_inputs = [audio_wav]
    speech_dict = processor.prepare_speech_inputs(speech_inputs, return_tensors="pt", dtype=load_dtype)
    padded_speeches = speech_dict["padded_speeches"].to(args.device)
    speech_masks = speech_dict["speech_masks"].to(args.device)

    # Convert to tensors
    lm_ids_tensor = torch.tensor([lm_input_ids], dtype=torch.long, device=args.device)
    lm_attn_mask = torch.ones_like(lm_ids_tensor)
    lm_speech_mask_tensor = torch.tensor([lm_speech_input_mask], dtype=torch.bool, device=args.device)

    tts_lm_ids_tensor = torch.tensor([tts_lm_input_ids], dtype=torch.long, device=args.device)
    tts_lm_attn_mask = torch.ones_like(tts_lm_ids_tensor)
    tts_lm_speech_mask_tensor = torch.tensor([tts_lm_speech_input_mask], dtype=torch.bool, device=args.device)

    # Build input embeddings with speech mixed in
    print("Building embeddings with voice audio...")
    embed_layer = model.model.get_input_embeddings()

    def build_embeds_with_speech(input_ids, speech_input_mask, padded_speeches, speech_masks_t):
        """Replace speech token positions with encoded audio embeddings."""
        embeds = embed_layer(input_ids)
        # Encode the audio through the acoustic tokenizer
        with torch.no_grad():
            # Get the VAE encoded speech
            acoustic_tokenizer = model.acoustic_tokenizer
            speech_input = padded_speeches  # (1, T)
            if speech_input.dim() == 2:
                speech_input = speech_input.unsqueeze(1)  # (1, 1, T)
            encoded = acoustic_tokenizer.encode(speech_input)  # returns latent
            if isinstance(encoded, tuple):
                encoded = encoded[0]
            # encoded shape: (1, D, L) where L = vae_tok_len
            encoded = encoded.squeeze(0).transpose(0, 1)  # (L, D)

            # Project through connector
            acoustic_connector = model.acoustic_connector
            speech_embeds = acoustic_connector(encoded)  # (L, H)
            speech_embeds = speech_embeds.unsqueeze(0)  # (1, L, H)

        # Place speech embeddings at the masked positions
        speech_positions = speech_input_mask[0].nonzero(as_tuple=True)[0]
        assert len(speech_positions) == speech_embeds.shape[1], \
            f"Mismatch: {len(speech_positions)} positions vs {speech_embeds.shape[1]} embeddings"
        embeds[0, speech_positions] = speech_embeds[0].to(embeds.dtype)
        return embeds

    lm_embeds = build_embeds_with_speech(lm_ids_tensor, lm_speech_mask_tensor, padded_speeches, speech_masks)

    # Run LM forward to get KV cache
    print("Running LM prefill...")
    with torch.no_grad():
        lm_outputs = model.forward_lm(
            inputs_embeds=lm_embeds,
            attention_mask=lm_attn_mask,
            use_cache=True,
            return_dict=True,
        )

    # Build TTS LM embeddings
    tts_lm_embeds = build_embeds_with_speech(tts_lm_ids_tensor, tts_lm_speech_mask_tensor, padded_speeches, speech_masks)

    # Add type embeddings for TTS LM
    tts_text_masks = (~tts_lm_speech_mask_tensor).long()  # text=1, speech=0
    tts_lm_embeds = tts_lm_embeds + model.model.tts_input_types(tts_text_masks)

    print("Running TTS LM prefill...")
    with torch.no_grad():
        # For TTS LM, we need lm_last_hidden_state
        # The TTS LM takes the LM's hidden states for the text portion
        tts_lm_outputs = model.model.tts_language_model(
            inputs_embeds=tts_lm_embeds,
            attention_mask=tts_lm_attn_mask,
            use_cache=True,
            return_dict=True,
        )

    # Create negative prompt caches (single token)
    neg_text_input_id = tokenizer.convert_tokens_to_ids("<|image_pad|>")
    neg_ids = torch.tensor([[neg_text_input_id]], dtype=torch.long, device=args.device)
    neg_attn = torch.ones_like(neg_ids)

    print("Running negative LM prefill...")
    with torch.no_grad():
        neg_embeds = embed_layer(neg_ids)
        neg_lm_outputs = model.forward_lm(
            inputs_embeds=neg_embeds,
            attention_mask=neg_attn,
            use_cache=True,
            return_dict=True,
        )

        neg_tts_embeds = embed_layer(neg_ids) + model.model.tts_input_types(torch.ones_like(neg_ids))
        neg_tts_lm_outputs = model.model.tts_language_model(
            inputs_embeds=neg_tts_embeds,
            attention_mask=neg_attn,
            use_cache=True,
            return_dict=True,
        )

    # Package the cached outputs
    all_prefilled = {
        "lm": {
            "last_hidden_state": lm_outputs.last_hidden_state.cpu(),
            "past_key_values": lm_outputs.past_key_values,
        },
        "tts_lm": {
            "last_hidden_state": tts_lm_outputs.last_hidden_state.cpu() if hasattr(tts_lm_outputs, 'last_hidden_state') else tts_lm_outputs[0].cpu(),
            "past_key_values": tts_lm_outputs.past_key_values if hasattr(tts_lm_outputs, 'past_key_values') else tts_lm_outputs[1],
        },
        "neg_lm": {
            "last_hidden_state": neg_lm_outputs.last_hidden_state.cpu(),
            "past_key_values": neg_lm_outputs.past_key_values,
        },
        "neg_tts_lm": {
            "last_hidden_state": neg_tts_lm_outputs.last_hidden_state.cpu() if hasattr(neg_tts_lm_outputs, 'last_hidden_state') else neg_tts_lm_outputs[0].cpu(),
            "past_key_values": neg_tts_lm_outputs.past_key_values if hasattr(neg_tts_lm_outputs, 'past_key_values') else neg_tts_lm_outputs[1],
        },
    }

    # Move KV caches to CPU for saving
    for key in all_prefilled:
        kv = all_prefilled[key]["past_key_values"]
        if hasattr(kv, 'to'):
            all_prefilled[key]["past_key_values"] = kv

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(all_prefilled, output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nVoice preset saved to {output_path} ({size_mb:.1f} MB)")
    print(f"Audio duration: {audio_duration:.1f}s → {vae_tok_len} tokens")

if __name__ == "__main__":
    main()
