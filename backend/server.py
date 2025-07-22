import torch
import whisper
import os
import json
from flask import Flask, request, jsonify
from pyannote.audio import Pipeline
from pydub import AudioSegment
import tempfile
from typing import List, Dict, Any
import glob
from pathlib import Path

app = Flask(__name__)

class SpeakerDiarizationService:
    def __init__(self):
        """Khởi tạo service cho speaker diarization và ASR"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Sử dụng device: {self.device}")
        
        # Khởi tạo diarization pipeline
        print("Đang tải diarization model...")
        self.diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token="your-hugging-face-token"   # like "hf_abcxyz..."
        )
        self.diarization_pipeline.to(torch.device(self.device))
        
        # Khởi tạo ASR model (Whisper)
        print("Đang tải ASR model...")
        self.transcriber = whisper.load_model("medium")
        
        print("Đã khởi tạo xong các model!")
    
    def diarize(self, audio_path: str, num_speakers: int = 2) -> List[Dict[str, Any]]:
        """
        Thực hiện speaker diarization
        
        Args:
            audio_path (str): Đường dẫn đến file audio
            num_speakers (int): Số lượng speaker
            
        Returns:
            List[Dict]: Danh sách các segments với thông tin speaker và thời gian
        """
        try:
            print(f"Đang phân đoạn người nói cho file: {audio_path}")
            diarization = self.diarization_pipeline(audio_path, num_speakers=num_speakers)
            
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "speaker": speaker,
                    "start": turn.start,
                    "end": turn.end
                })
            
            print(f"Đã phân tách được {len(segments)} segments")
            return segments
            
        except Exception as e:
            print(f"Lỗi khi thực hiện diarization: {str(e)}")
            raise e
    
    def process_segments(self, audio_path: str, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Xử lý từng segment để chuyển đổi thành text
        
        Args:
            audio_path (str): Đường dẫn đến file audio gốc
            segments (List[Dict]): Danh sách các segments từ diarization
            
        Returns:
            List[Dict]: Kết quả với text cho từng segment
        """
        try:
            print("Đang xử lý các đoạn thoại...")
            audio = AudioSegment.from_wav(audio_path)
            results = []
            
            for i, seg in enumerate(segments):
                if abs(seg["start"] - seg["end"]) < 1:
                    continue
                else:
                    start_ms = int(seg["start"] * 1000)
                    end_ms = int(seg["end"] * 1000)
                    segment = audio[start_ms:end_ms]
                
                    # Tạo temporary file cho segment
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                        segment.export(temp_file.name, format="wav")
                        
                        # Thực hiện ASR
                        result = self.transcriber.transcribe(temp_file.name, language="vi")
                        
                        # Xóa temporary file
                        os.unlink(temp_file.name)
                        
                        results.append({
                            "segment_id": i + 1,
                            "file": f"segment_{i+1}_{seg['speaker']}.wav",
                            "speaker": seg["speaker"],
                            "start_time": seg["start"],
                            "end_time": seg["end"],
                            "text": result["text"].strip()
                        })
            
            return results
            
        except Exception as e:
            print(f"Lỗi khi xử lý segments: {str(e)}")
            raise e
    
    def process_audio(self, audio_path: str, num_speakers: int = 2) -> Dict[str, Any]:
        """
        Xử lý hoàn chỉnh audio: diarization + ASR
        
        Args:
            audio_path (str): Đường dẫn đến file audio
            num_speakers (int): Số lượng speaker
            
        Returns:
            Dict[str, Any]: Kết quả hoàn chỉnh
        """
        try:
            # Kiểm tra file tồn tại
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Không tìm thấy file audio: {audio_path}")
            
            # Thực hiện diarization
            segments = self.diarize(audio_path, num_speakers)
            
            # Xử lý từng segment
            results = self.process_segments(audio_path, segments)
            
            return {
                "success": True,
                "audio_path": audio_path,
                "num_speakers": num_speakers,
                "total_segments": len(segments),
                "segments": segments,
                "transcriptions": results
            }
            
        except Exception as e:
            print(f"Lỗi khi xử lý audio: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

def get_latest_audio_file(tmp_dir: str = "../tmp") -> str:
    """
    Lấy file audio mới nhất trong thư mục tmp
    
    Args:
        tmp_dir (str): Đường dẫn đến thư mục tmp
        
    Returns:
        str: Đường dẫn đến file audio mới nhất
    """
    try:
        # Tìm tất cả file audio trong thư mục tmp
        audio_patterns = ["*.wav", "*.mp3", "*.m4a", "*.flac"]
        audio_files = []
        
        for pattern in audio_patterns:
            audio_files.extend(glob.glob(os.path.join(tmp_dir, pattern)))
        
        if not audio_files:
            raise FileNotFoundError("Không tìm thấy file audio nào trong thư mục tmp")
        
        # Sắp xếp theo thời gian tạo file (mới nhất trước)
        audio_files.sort(key=os.path.getctime, reverse=True)
        
        latest_file = audio_files[0]
        print(f"Tìm thấy file audio mới nhất: {latest_file}")
        
        return latest_file
        
    except Exception as e:
        print(f"Lỗi khi tìm file audio mới nhất: {str(e)}")
        raise e

# Khởi tạo service
diarization_service = SpeakerDiarizationService()

@app.route('/health', methods=['GET'])
def health_check():
    """Kiểm tra trạng thái server"""
    return jsonify({
        "status": "healthy",
        "device": diarization_service.device,
        "models_loaded": True
    })

@app.route('/process_audio', methods=['POST'])
def process_audio():
    """
    API endpoint để xử lý file audio mới nhất trong thư mục tmp
    Không cần truyền JSON vào body
    """
    try:
        # Lấy file audio mới nhất từ thư mục tmp
        audio_path = get_latest_audio_file()
        num_speakers = 2  # Mặc định 2 speaker
        
        print(f"Đang xử lý file: {audio_path}")
        
        # Xử lý audio
        result = diarization_service.process_audio(audio_path, num_speakers)
        
        # Sau khi xử lý xong thì xóa file audio
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                print(f"Đã xóa file tạm: {audio_path}")
            except Exception as e:
                print(f"Lỗi khi xóa file tạm: {e}")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/get_transcript', methods=['GET'])
def get_transcript():
    """
    API endpoint để lấy transcript dạng text đơn giản từ file mới nhất
    """
    try:
        # Lấy file audio mới nhất từ thư mục tmp
        audio_path = get_latest_audio_file()
        num_speakers = 2  # Mặc định 2 speaker
        
        # Xử lý audio
        result = diarization_service.process_audio(audio_path, num_speakers)
        
        if not result["success"]:
            return jsonify(result), 500
        
        # Tạo transcript đơn giản
        transcript = ""
        for trans in result["transcriptions"]:
            transcript += f"{trans['speaker']}: {trans['text']}\n"
        
        # Xóa file sau khi xử lý
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                print(f"Đã xóa file tạm: {audio_path}")
            except Exception as e:
                print(f"Lỗi khi xóa file tạm: {e}")
        
        return jsonify({
            "success": True,
            "transcript": transcript.strip()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/test', methods=['GET'])
def test():
    """Test endpoint"""
    return jsonify({
        "message": "Server đang hoạt động!",
        "device": diarization_service.device
    })

if __name__ == '__main__':
    print("Khởi động server...")
    print("Các endpoint có sẵn:")
    print("- POST /process_audio: Xử lý file mới nhất trong tmp")
    print("- GET /get_transcript: Lấy transcript từ file mới nhất")
    print("- GET /health: Kiểm tra trạng thái server")
    print("- GET /test: Test endpoint")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
