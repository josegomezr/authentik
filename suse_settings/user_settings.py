# User-defined settings
import os
import json

AWS_S3_OBJECT_PARAMETERS = {}

if 'AWS_S3_OBJECT_PARAMETERS' in os.environ:
    try:
        AWS_S3_OBJECT_PARAMETERS = json.loads(os.environ['AWS_S3_OBJECT_PARAMETERS'])
    except json.decoder.JSONDecodeError:
        pass
