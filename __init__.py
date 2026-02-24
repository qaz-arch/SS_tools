NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    from .duck_encode_node import NODE_CLASS_MAPPINGS as STEG_NODES, NODE_DISPLAY_NAME_MAPPINGS as STEG_DISPLAY
    NODE_CLASS_MAPPINGS.update(STEG_NODES)
    NODE_DISPLAY_NAME_MAPPINGS.update(STEG_DISPLAY)
except Exception as e:
    print(f"❌ SS_tools Import Error (Encode): {e}")

try:
    from .duck_decode_node import NODE_CLASS_MAPPINGS as DECODE_NODES, NODE_DISPLAY_NAME_MAPPINGS as DECODE_DISPLAY
    NODE_CLASS_MAPPINGS.update(DECODE_NODES)
    NODE_DISPLAY_NAME_MAPPINGS.update(DECODE_DISPLAY)
except Exception as e:
    print(f"❌ SS_tools Import Error (Decode): {e}")

try:
    from .duck_qr_encoder_node import NODE_CLASS_MAPPINGS as QR_NODES, NODE_DISPLAY_NAME_MAPPINGS as QR_DISPLAY
    NODE_CLASS_MAPPINGS.update(QR_NODES)
    NODE_DISPLAY_NAME_MAPPINGS.update(QR_DISPLAY)
except ImportError:
    print("ℹ️ SS_tools: Duck QR Encoder node not found. Skipping.")
except Exception as e:
    print(f"❌ SS_tools Import Error (QR): {e}")

WEB_DIRECTORY = "./js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
