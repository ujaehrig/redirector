"""AWS Lambda handler using Mangum."""

import warnings

# Mangum uses asyncio.get_event_loop() which is deprecated in Python 3.12+
# but works fine in Lambda's runtime environment.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from mangum import Mangum

from redirector.main import create_application

app = create_application()

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    handler = Mangum(app)
