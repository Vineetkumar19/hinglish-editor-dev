"""Keep speech-model lifetime separate from the subsequent heading model."""
import gc


def transcribe_words(factory, model_path, device, wav, script, duration, check, progress):
    speech=None; segments=None
    observed=[]
    try:
        speech=factory(model_path,device=device,compute_type='float16' if device=='cuda' else 'int8',cpu_threads=6,local_files_only=True)
        segments,_=speech.transcribe(str(wav),beam_size=5,temperature=0,word_timestamps=True,vad_filter=True,condition_on_previous_text=False,initial_prompt=script[:1600])
        for segment in segments:
            check()
            for word in segment.words or []:
                if word.end>word.start and word.probability>=.20:
                    for part in word.word.split():
                        observed.append({'text':part,'start':max(0,float(word.start)),'end':min(duration,float(word.end)),'probability':float(word.probability)})
            progress('Matching words to the narration…',18+35*min(1,segment.end/duration))
        return observed
    finally:
        # A suspended generator can retain the model after cancellation. Release
        # it before the LLM is loaded. CTranslate2 does not use torch's allocator;
        # importing torch just to clear its empty cache needlessly raises RAM use.
        try:
            if segments is not None and hasattr(segments,'close'): segments.close()
        finally:
            segments=None; speech=None
            gc.collect()
