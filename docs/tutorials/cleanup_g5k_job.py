import logging
import sys

import enoslib as en

en.init_logging(level=logging.DEBUG)

job_name = sys.argv[1]
conf = en.G5kConf.from_settings(job_name=job_name)
provider = en.G5k(conf)
provider.destroy()
exit(1)
