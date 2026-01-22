# User-defined settings
from authentik.lib.config import CONFIG

# S3 Configuration
AWS_S3_OBJECT_PARAMETERS = CONFIG.get_dict_from_b64_json("suse.aws_s3_object_parameters", {})
CONFIG.log("info", "Loaded AWS_S3_OBJECT_PARAMETERS={}".format(AWS_S3_OBJECT_PARAMETERS))

# OTP settings
OTP_TOTP_ISSUER = CONFIG.get("suse.otp_totp_issuer", None)
OTP_TOTP_IMAGE = CONFIG.get("suse.otp_totp_image", None)
OTP_TOTP_THROTTLE_FACTOR = CONFIG.get_int("suse.otp_totp_throttle_factor", 1)
OTP_TOTP_SYNC = CONFIG.get_bool("suse.otp_totp_sync", True)

CONFIG.log("info", "Loaded user_settings")
