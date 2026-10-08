import io,pathlib,tempfile,unittest,wave,json,time
from voice_server import VoiceService,signature,valid_wav,usable_transcript,prepare_audio
class VoiceTests(unittest.TestCase):
    def wav(self,rate=16000):
        out=io.BytesIO()
        with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b'\1\0'*8000)
        return out.getvalue()
    def test_format_and_truncation(self):
        self.assertTrue(valid_wav(self.wav()));self.assertFalse(valid_wav(self.wav(8000)));self.assertFalse(valid_wav(self.wav()[:-100]));self.assertFalse(valid_wav(b'not audio'))
    def test_authentication_idempotency_and_real_answer_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            service=VoiceService('a'*64,pathlib.Path(tmp),lambda body,id:calls.append(id) or {'question':'cuantos','answer':'Hoy se han atendido 12 pacientes.'})
            body=self.wav();id='1'*32;sig=signature(service.key,id,body)
            self.assertEqual(service.accept(id,'0'*64,body),401)
            self.assertEqual(service.accept(id,sig,body+b'wrong'),401)
            self.assertEqual(service.accept(id,sig,body),202)
            service.executor.shutdown(wait=True)
            event=json.loads((pathlib.Path(tmp)/'pending'/f'{id}.json').read_text())
            self.assertEqual(event['voice_reply_id'],id);self.assertIn('12 pacientes',event['message'])
            self.assertEqual(service.accept(id,sig,body),200);self.assertEqual(calls,[id])
    def test_noise_hallucinations_are_not_sent_as_questions(self):
        self.assertFalse(usable_transcript('Bueno, '+ 'pues, '*35))
        self.assertFalse(usable_transcript('Subtítulos realizados por la comunidad de Amara.org'))
        self.assertTrue(usable_transcript('¿Cuántos pacientes se han atendido hoy?'))
        self.assertTrue(usable_transcript('¿Quién hizo los subtítulos de este video?'))
    def test_audio_gain_preserves_pcm_format_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'input.wav';out=io.BytesIO()
            with wave.open(out,'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes((1000).to_bytes(2,'little',signed=True)*8000)
            p.write_bytes(out.getvalue());prepare_audio(p)
            self.assertTrue(valid_wav(p.read_bytes()))
            with wave.open(str(p),'rb') as w:self.assertEqual(int.from_bytes(w.readframes(1),'little',signed=True),8000)
    def test_busy_does_not_queue_second_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=VoiceService('a'*64,pathlib.Path(tmp));service.busy=True
            body=self.wav();id='2'*32
            self.assertEqual(service.accept(id,signature(service.key,id,body),body),409)
            service.executor.shutdown()
if __name__=='__main__':unittest.main()
