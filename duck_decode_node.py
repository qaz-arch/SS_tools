import io
import os
import struct
import numpy as np
import subprocess
from typing import Any, List
from PIL import Image
import torch
try:
    import moviepy
    from moviepy.editor import VideoFileClip
except ImportError:
    try:
        import moviepy
        from moviepy import VideoFileClip
    except ImportError:
        print("❌ MoviePy import failed in duck_decode_node.")
        VideoFileClip = None
try:
    import folder_paths  # type: ignore
except Exception:
    folder_paths = None

CATEGORY = "SSTool"
WATERMARK_SKIP_W_RATIO = 0.40
WATERMARK_SKIP_H_RATIO = 0.08

def _extract_payload_with_k(arr: np.ndarray, k: int) -> bytes:
    h, w, c = arr.shape
    skip_w = int(w * WATERMARK_SKIP_W_RATIO)
    skip_h = int(h * WATERMARK_SKIP_H_RATIO)
    mask2d = np.ones((h, w), dtype=bool)
    if skip_w > 0 and skip_h > 0:
        mask2d[:skip_h, :skip_w] = False
    mask3d = np.repeat(mask2d[:, :, None], c, axis=2)
    flat = arr.reshape(-1)
    idxs = np.flatnonzero(mask3d.reshape(-1))
    vals = (flat[idxs] & ((1 << k) - 1)).astype(np.uint8)
    ub = np.unpackbits(vals, bitorder="big").reshape(-1, 8)[:, -k:]
    bits = ub.reshape(-1)
    if len(bits) < 32:
        raise ValueError("Insufficient image data. 图像数据不足")
    len_bits = bits[:32]
    length_bytes = np.packbits(len_bits, bitorder="big").tobytes()
    header_len = struct.unpack(">I", length_bytes)[0]
    total_bits = 32 + header_len * 8
    if header_len <= 0 or total_bits > len(bits):
        raise ValueError("Payload length invalid. 载荷长度异常")
    payload_bits = bits[32:32 + header_len * 8]
    return np.packbits(payload_bits, bitorder="big").tobytes()

def _generate_key_stream(password: str, salt: bytes, length: int) -> bytes:
    import hashlib
    key_material = (password + salt.hex()).encode("utf-8")
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key_material + str(counter).encode("utf-8")).digest())
        counter += 1
    return bytes(out[:length])

def _parse_header(header: bytes, password: str):
    idx = 0
    if len(header) < 1:
        raise ValueError("Header corrupted. 文件头损坏")
    has_pwd = header[0] == 1
    idx += 1
    pwd_hash = b""
    salt = b""
    if has_pwd:
        if len(header) < idx + 32 + 16:
            raise ValueError("Header corrupted. 文件头损坏")
        pwd_hash = header[idx:idx + 32]; idx += 32
        salt = header[idx:idx + 16]; idx += 16
    if len(header) < idx + 1:
        raise ValueError("Header corrupted. 文件头损坏")
    ext_len = header[idx]; idx += 1
    if len(header) < idx + ext_len + 4:
        raise ValueError("Header corrupted. 文件头损坏")
    ext = header[idx:idx + ext_len].decode("utf-8", errors="ignore"); idx += ext_len
    data_len = struct.unpack(">I", header[idx:idx + 4])[0]; idx += 4
    data = header[idx:]
    if len(data) != data_len:
        raise ValueError("Data length mismatch. 数据长度不匹配")
    if not has_pwd:
        return data, ext
    if not password:
        raise ValueError("Password required. 需要密码")
    import hashlib
    check_hash = hashlib.sha256((password + salt.hex()).encode("utf-8")).digest()
    if check_hash != pwd_hash:
        raise ValueError("Wrong password. 密码错误")
    ks = _generate_key_stream(password, salt, len(data))
    plain = bytes(a ^ b for a, b in zip(data, ks))
    return plain, ext

def _tensor_to_pil(image: torch.Tensor) -> Image.Image:
    if image.dim() == 4:
        image = image[0]
    arrf = image.detach().cpu().numpy() * 255.0
    arru = np.rint(np.clip(arrf, 0, 255)).astype(np.uint8)
    if arru.ndim == 2:
        arru = np.stack([arru, arru, arru], axis=-1)
        return Image.fromarray(arru, mode="RGB")
    if arru.shape[-1] == 3:
        return Image.fromarray(arru, mode="RGB")
    if arru.shape[-1] == 4:
        return Image.fromarray(arru, mode="RGBA")
    if arru.shape[-1] > 4:
        return Image.fromarray(arru[..., :3], mode="RGB")
    return Image.fromarray(np.repeat(arru[..., :1], 3, axis=-1), mode="RGB")


def _pil_to_tensor(image: Image.Image) -> torch.Tensor:
    arr = np.array(image).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]

def binpng_bytes_to_mp4_bytes(p: str) -> bytes:
    img = Image.open(p).convert("RGB")
    arr = np.array(img).astype(np.uint8)
    flat = arr.reshape(-1, 3).reshape(-1)
    return flat.tobytes().rstrip(b"\x00")

class DuckDecodeNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),

            },
            "optional": {
                "password": ("STRING", {"default": "", "multiline": False}),

            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING", "INT", "STRING")
    RETURN_NAMES = ("images", "audio", "file_path", "fps", "text_output")
    FUNCTION = "decode"
    CATEGORY = CATEGORY

    def decode(self, image: torch.Tensor, password: str = "",Notes: str = ""):
        pil = _tensor_to_pil(image)
        arr = np.array(pil.convert("RGB")).astype(np.uint8)
        header = None
        raw = None
        ext = None
        last_err = None
        text_output = ""
        for k in (2, 6, 8):
            try:
                header = _extract_payload_with_k(arr, k)
                raw, ext = _parse_header(header, password)
                break
            except Exception as e:
                last_err = e
                continue
        if raw is None:
            raise last_err or RuntimeError("解析失败")

        base_dir = folder_paths.get_output_directory() if folder_paths else os.getcwd()
        os.makedirs(base_dir, exist_ok=True)
        name = "duck_recovered"
        out_path = os.path.join(base_dir, name)

        final_path = ""
        final_ext = ext
        if ext.endswith(".binpng"):
            tmp_png = out_path + ".binpng"
            with open(tmp_png, "wb") as f:
                f.write(raw)
            mp4_bytes = binpng_bytes_to_mp4_bytes(tmp_png)
            os.unlink(tmp_png)
            final_path = out_path + ".mp4"
            with open(final_path, "wb") as f:
                f.write(mp4_bytes)
            final_ext = "mp4"
        else:
            final_path = out_path + ("." + ext if not ext.startswith(".") else ext)
            with open(final_path, "wb") as f:
                f.write(raw)
            
            if ext.lower() == "txt":
                try:
                    text_output = raw.decode("utf-8")
                except Exception:
                    # try other encoding or ignore
                    try:
                        text_output = raw.decode("gbk")
                    except Exception:
                        text_output = f"Error decoding text content from {final_path}"

        img_tensor = None
        audio_out = None
        fps_out = 0
        if final_ext.lower() == "png":
            img_tensor = _pil_to_tensor(Image.open(final_path).convert("RGB"))
        elif final_ext.lower() == "mp4":
            clip = VideoFileClip(final_path)
            fps_out = int(round(clip.fps)) if clip.fps else 0
            # 优化：直接使用 reader.nframes 或 duration * fps 计算总帧数，不再依赖 ffprobe
            frame_count = 0
            if hasattr(clip, 'reader') and hasattr(clip.reader, 'nframes') and clip.reader.nframes:
                 frame_count = clip.reader.nframes
            else:
                 # Fallback: 使用 round 避免浮点精度导致的少帧问题
                 frame_count = int(round(clip.duration * max(1, fps_out)))
            
            img_tensor = None
            
            if frame_count > 0:
                try:
                    # 获取第一帧以确定尺寸
                    # 优先使用 iter_frames 获取第一帧，避免 seek
                    first_frame_iter = clip.iter_frames(fps=None)
                    first_frame = next(first_frame_iter)
                    h, w, c = first_frame.shape
                    # 预分配内存：直接申请最终所需空间，避免 List + Stack 的双倍内存峰值
                    img_tensor = torch.zeros((frame_count, h, w, c), dtype=torch.float32)
                except Exception as e:
                    print(f"Error initializing video tensor: {e}")
                    img_tensor = None

            if img_tensor is None:
                img_tensor = torch.zeros((1, 1, 1, 3), dtype=torch.float32)
            else:
                # 使用 iter_frames 顺序读取，比 get_frame(t) 更快更准
                # fps=None 表示输出原始帧
                for i, frame in enumerate(clip.iter_frames(fps=None)):
                    if i >= frame_count:
                        break
                    try:
                        # 直接写入预分配位置，不产生额外的 Tensor 副本
                        # 修复 numpy 不可写警告：先复制一份数据
                        frame_copy = frame.copy()
                        img_tensor[i] = torch.from_numpy(frame_copy).float().div(255.0)
                    except Exception as e:
                        print(f"Frame decode error at index {i}: {e}")
                        continue
            
            if clip.audio is not None:
                # todo 这个部分与RH平台存在包冲突
                try:
                    sr_attr = getattr(clip.audio, "fps", None)
                    sr = int(round(sr_attr)) if sr_attr else 44100
                    
                    audio_np = None
                    
                    # 判断 MoviePy 版本，如果是 1.x 则直接使用 ffmpeg 提取
                    is_moviepy_1x = False
                    if hasattr(moviepy, "__version__") and moviepy.__version__.startswith("1."):
                        is_moviepy_1x = True
                    
                    if is_moviepy_1x:
                        try:
                            # 使用 ffmpeg 直接提取音频为 raw float32 pcm
                            # -vn: 禁用视频
                            # -f f32le: 输出格式 float32 little endian
                            # -acodec pcm_f32le: 编码器
                            # -ar {sr}: 采样率
                            # -ac 2: 声道数 (强制双声道以简化处理，或者先探测？这里假设双声道通用)
                            # -: 输出到 stdout
                            cmd = [
                                "ffmpeg",
                                "-v", "error",
                                "-i", final_path,
                                "-vn",
                                "-f", "f32le",
                                "-acodec", "pcm_f32le",
                                "-ar", str(sr),
                                "-ac", "2",
                                "-"
                            ]
                            # 运行命令并获取输出
                            process = subprocess.run(cmd, capture_output=True, check=True)
                            raw_audio = process.stdout
                            
                            if raw_audio:
                                audio_np = np.frombuffer(raw_audio, dtype=np.float32)
                                audio_np = audio_np.reshape(-1, 2) # 重塑为 (Samples, Channels=2)
                        except Exception as e:
                            print(f"FFmpeg audio extraction failed: {e}")
                            audio_np = None

                    # 如果不是 1.x 或者 ffmpeg 失败，尝试原有的 moviepy 逻辑 (作为 fallback 或主逻辑)
                    if audio_np is None and not is_moviepy_1x:
                        try:
                            audio_np = clip.audio.to_soundarray(fps=sr, nbytes=4)
                        except Exception:
                            pass
                        
                        if audio_np is None:
                            # Fallback: 手动读取音频块
                            try:
                                chunks = []
                                iterator = None
                                try:
                                    iterator = clip.audio.iter_chunks(fps=sr, nbytes=4, quantize=False)
                                except TypeError:
                                    iterator = clip.audio.iter_chunks(fps=sr)
                                
                                if iterator:
                                    for chunk in iterator:
                                        chunks.append(chunk)
                                
                                if len(chunks) > 0:
                                    audio_np = np.vstack(chunks)
                            except Exception as e:
                                print(f"Manual audio chunk read failed: {e}")
                        
                        if audio_np is None:
                             try:
                                 audio_np = clip.audio.to_soundarray()
                             except Exception:
                                 pass

                    if audio_np is None:
                         print("Audio decoding completely failed, returning silent audio.")
                         audio_np = np.zeros((sr, 2), dtype=np.float32)

                    # 归一化处理
                    max_val = np.max(np.abs(audio_np))
                    if max_val > 0:
                        audio_np = audio_np / max_val

                    if len(audio_np.shape) == 1:
                        audio_np = np.expand_dims(audio_np, axis=1)
                    wf = torch.from_numpy(audio_np.T.astype(np.float32)).unsqueeze(0)
                    audio_out = {"waveform": wf, "sample_rate": sr}
                except Exception as e:
                    audio_out = None
                    print(f"Audio decode error: {e}")
            clip.close()
        else:
            img_tensor = torch.zeros((1, 1, 1, 3), dtype=torch.float32)

        return (img_tensor, audio_out, final_path, fps_out, text_output)


NODE_CLASS_MAPPINGS = {"DuckDecodeNode": DuckDecodeNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DuckDecodeNode": "鸭鸭图 SuperSecureMediaProtectionDec媒体内容保护 解码V1.2"}
