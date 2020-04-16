import os

DEBUG = int(os.environ.get("DEBUG", 0))
PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
GRAYLOG_LOGGING = int(os.environ.get("GRAYLOG_LOGGING", 0))

# =================================
# WHITE LIST OF MONITORING METRICS
# =================================
# For ceilometer, see: https://docs.openstack.org/ceilometer/latest/admin/telemetry-measurements.html
METRICS_WHITE_LIST = {
    "openstack": ['memory', 'memory.usage', 'memory.resident', 'memory.bandwidth.total',
                  'memory.bandwidth.local',
                  'memory.swap.in', 'memory.swap.out', 'memory_util',
                  'cpu', 'cpu_util', 'cpu.delta', 'vcpus', 'cpu_l3_cache', 'perf.cpu.cycles',
                  'network.incoming.bytes', 'network.incoming.bytes.rate', 'network.outgoing.bytes',
                  'network.outgoing.bytes.rate', 'network.incoming.packets',
                  'network.incoming.packets.rate',
                  'network.outgoing.packets', 'network.outgoing.packets.rate',
                  'network.incoming.packets.drop',
                  'network.outgoing.packets.drop', 'network.incoming.packets.error',
                  'network.outgoing.packets.error',
                  'disk.read.requests', 'disk.read.requests.rate', 'disk.write.requests',
                  'disk.write.requests.rate',
                  'disk.read.bytes', 'disk.read.bytes.rate', 'disk.write.bytes',
                  'disk.write.bytes.rate',
                  'disk.device.read.requests', 'disk.device.read.requests.rate',
                  'disk.device.write.requests',
                  'disk.device.write.requests.rate', 'disk.device.read.bytes',
                  'disk.device.read.bytes.rate',
                  'disk.device.write.bytes', 'disk.device.write.bytes.rate', 'disk.root.size',
                  'disk.ephemeral.size',
                  'disk.latency', 'disk.iops', 'disk.device.latency', 'disk.device.iops',
                  'disk.capacity', 'disk.usage',
                  'disk.allocation', 'disk.device.capacity', 'disk.device.allocation',
                  'disk.device.usage',
                  'disk.device.read.latency', 'disk.device.write.latency'],
    "opennebula": ['', ],
    "unikernels": ['*', ],
    "kubernetes": ['', ],
    "telegraf": ["bytes_recv", "bytes_sent", "drop_in", "drop_out", "err_in", "err_out",
                 "packets_recv", "packets_sent",
                 "icmp_inaddrmaskreps", "icmp_inaddrmasks", "icmp_incsumerrors",
                 "icmp_indestunreachs",
                 "icmp_inechoreps", "icmp_inechos", "icmp_inerrors", "icmp_inmsgs",
                 "icmp_inparmprobs",
                 "icmp_inredirects", "icmp_insrcquenchs", "icmp_intimeexcds",
                 "icmp_intimestampreps",
                 "icmp_intimestamps", "icmp_outaddrmaskreps", "icmp_outaddrmasks",
                 "icmp_outdestunreachs",
                 "icmp_outechoreps", "icmp_outechos", "icmp_outerrors", "icmp_outmsgs",
                 "icmp_outparmprobs",
                 "icmp_outredirects", "icmp_outsrcquenchs", "icmp_outtimeexcds",
                 "icmp_outtimestampreps",
                 "icmp_outtimestamps", "icmpmsg_intype3", "icmpmsg_outtype3", "ip_defaultttl",
                 "ip_forwarding",
                 "ip_forwdatagrams", "ip_fragcreates", "ip_fragfails", "ip_fragoks",
                 "ip_inaddrerrors", "ip_indelivers",
                 "ip_indiscards", "ip_inhdrerrors", "ip_inreceives", "ip_inunknownprotos",
                 "ip_outdiscards",
                 "ip_outnoroutes", "ip_outrequests", "ip_reasmfails", "ip_reasmoks",
                 "ip_reasmreqds", "ip_reasmtimeout",
                 "tcp_activeopens", "tcp_attemptfails", "tcp_currestab", "tcp_estabresets",
                 "tcp_incsumerrors",
                 "tcp_inerrs", "tcp_insegs", "tcp_maxconn", "tcp_outrsts", "tcp_outsegs",
                 "tcp_passiveopens",
                 "tcp_retranssegs", "tcp_rtoalgorithm", "tcp_rtomax", "tcp_rtomin",
                 "udp_incsumerrors",
                 "udp_indatagrams", "udp_inerrors", "udp_noports", "udp_outdatagrams",
                 "udp_rcvbuferrors",
                 "udp_sndbuferrors", "udplite_incsumerrors", "udplite_indatagrams",
                 "udplite_inerrors",
                 "udplite_noports", "udplite_outdatagrams", "udplite_rcvbuferrors",
                 "udplite_sndbuferrors"],
}

# =================================
# KAFKA SETTINGS
# =================================
KAFKA_SERVER = "{}:{}".format(os.environ.get("KAFKA_HOST", "192.168.1.175"),
                              os.environ.get("KAFKA_PORT", "9092"))
KAFKA_CLIENT_ID = 'monitoring-data-translator'
KAFKA_API_VERSION = (1, 1, 0)
KAFKA_GROUP_ID = {"openstack": "MAPE_OS_TRANSLATOR_CG",
                  "opennebula": "MAPE_OPENNEBULA_TRANSLATOR_CG",
                  "kubernetes": "MAPE_K8S_TRANSLATOR_CG",
                  "unikernels": "MAPE_UNIKERNELS_TRANSLATOR_CG",
                  "telegraf": "MAPE_VCACHE_METRICS_CG",
                  "qoe_uc1": "MAPE_VTRANSCODER_QOE_CG",
                  "generic_metrics": "MAPE_GENERIC_METRICS_CG",
                  "vtranscoder3d": "MAPE_VTRANSCODER_METRICS_CG",
                  "vtranscoder3d_spectators": "MAPE_VTRANS_SPECTATORS_CG",
                  "vce": "MAPE_VCE_METRICS_CG", }
KAFKA_MONITORING_TOPICS = {"openstack": "nfvi.*.openstack",
                           "opennebula": "nfvi.*.opennebula",
                           "kubernetes": "nfvi.*.kubernetes", # fixme before deployment
                           "unikernels": "app.unikernels.jolokia",
                           "telegraf": "app.vcache.metrics",
                           "vtranscoder3d": ['1_metrics', '2_metrics', "app.vtranscoder3d.metrics"],
                           "vtranscoder3d_spectators": "spectators.vtranscoder3d.metrics",
                           "vce": "app.vce.metrics"}
KAFKA_TRANSLATION_TOPIC = os.environ.get("KAFKA_TRANSLATION_TOPIC", "ns.instances.trans")
KAFKA_EXECUTION_TOPIC = "ns.instances.exec"
KAFKA_TIMEOUT = 10  # seconds

# =================================
# OSM SETTINGS
# =================================
OSM_IP = os.environ.get("OSM_IP", "10.100.176.66")
OSM_ADMIN_CREDENTIALS = {"username": os.environ.get("OSM_USER", "admin"),
                         "password": os.environ.get("OSM_PWD", "osmpaswword")}
OSM_COMPONENTS = {"UI": 'http://{}:80'.format(OSM_IP),
                  "NBI-API": 'https://{}:9999'.format(OSM_IP),
                  "RO-API": 'http://{}:9090'.format(OSM_IP)}

# =================================
# REDIS SETTINGS
# =================================
REDIS_HOST = os.environ.get("REDIS_IP", "10.100.176.70")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_NFVI_DB = 0
REDIS_PASSWORD = None
REDIS_EXPIRATION_SECONDS = os.environ.get("REDIS_EXPIRATION_SEC", 1200)  # default: 20 minutes
# REDIS_SSL = False # default
# REDIS_SSL_KEYFILE = None # default
# REDIS_CERTFILE = None # default
# REDIS_SSL_CERT_REQS = u'required' # default
# REDIS_CA_CERTS = None # default

# =================================
# INFLUXDB SETTINGS
# =================================
# See InfluxDBClient class
INFLUX_DATABASES = {
    'default': {
        'ENGINE': 'influxdb',
        'NAME': os.environ.get("INFLUXDB_DB_NAME", 'monitoring'),
        'USERNAME': os.environ.get("INFLUXDB_USER", 'root'),
        'PASSWORD': os.environ.get("INFLUXDB_PWD", 'influxdbpassword'),
        'HOST': os.environ.get("INFLUXDB_IP", "192.168.1.175"),
        'PORT': os.environ.get("INFLUXDB_PORT", 8086)
    }
}

# =================================
# GRAYLOG SETTINGS
# =================================
GRAYLOG_HOST = os.environ.get("GRAYLOG_HOST", '192.168.1.175')
GRAYLOG_PORT = int(os.environ.get("GRAYLOG_PORT", 12201))

# ==================================
# LOGGING SETTINGS
# ==================================
# See more: https://docs.python.org/3.5/library/logging.config.html

DEFAULT_HANDLER_SETTINGS = {
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': "{}/logs/access.log".format(PROJECT_ROOT),
    'mode': 'w',
    'formatter': 'detailed',
    'level': 'DEBUG' if DEBUG else 'WARNING',
    'maxBytes': 4096 * 4096,
    'backupCount': 20,
}
if GRAYLOG_LOGGING:
    DEFAULT_HANDLER_SETTINGS = {
        'class': 'graypy.GELFUDPHandler',
        'formatter': 'detailed',
        'level': 'DEBUG' if DEBUG else 'WARNING',
        'host': GRAYLOG_HOST,
        'port': GRAYLOG_PORT
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'detailed': {
            'class': 'logging.Formatter',
            'format': "[%(asctime)s] - [%(name)s:%(lineno)s] - [%(levelname)s] %(message)s",
        },
        'simple': {
            'class': 'logging.Formatter',
            'format': '%(name)-15s %(levelname)-8s %(processName)-10s %(message)s'
        }
    },
    'handlers': {
        'vtranscoder3d': DEFAULT_HANDLER_SETTINGS,
        'vtranscoder3d_spectators': DEFAULT_HANDLER_SETTINGS,
        'vcache': DEFAULT_HANDLER_SETTINGS,
        'vce': DEFAULT_HANDLER_SETTINGS,
        'kubernetes': DEFAULT_HANDLER_SETTINGS,
        'opennebula': DEFAULT_HANDLER_SETTINGS,
        'openstack': DEFAULT_HANDLER_SETTINGS,
        'translator': DEFAULT_HANDLER_SETTINGS,
        'soapi': DEFAULT_HANDLER_SETTINGS,
        'errors': DEFAULT_HANDLER_SETTINGS
    },
    'loggers': {
        'vtranscoder3d': {
            'handlers': ['vtranscoder3d']
        },
        'vtranscoder3d_spectators': {
            'handlers': ['vtranscoder3d_spectators']
        },
        'vcache': {
            'handlers': ['vcache']
        },
        'vce': {
            'handlers': ['vce']
        },
        'kubernetes': {
            'handlers': ['kubernetes']
        },
        'opennebula': {
            'handlers': ['opennebula']
        },
        'openstack': {
            'handlers': ['openstack']
        },
        'translator': {
            'handlers': ['translator']
        },
        'soapi': {
            'handlers': ['soapi']
        },
        'errors': {
            'handlers': ['errors']
        }
    },
    'root': {
        'level': 'WARNING',
        'handlers': [
            'vtranscoder3d',
            'vtranscoder3d_spectators',
            'vcache',
            'vce',
            'kubernetes',
            'opennebula',
            'openstack',
            'translator',
            'soapi',
            'errors',
        ]
    },
}
