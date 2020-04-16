class VduWithIpNotFound(Exception):
    """Not found VDU with given IP"""
    pass


class VduNotFound(Exception):
    """Not found VDU with given UUID"""
    pass


class VnfNotFound(Exception):
    """Not found VDU with given UUID"""
    pass


class VduUuidDoesNotExist(Exception):
    """Not found VDU with given UUID"""
    pass


class OsmInfoNotFound(Exception):
    """OSM data not fprovided for VDU with given UUID"""
    pass


class VnfIndexInvalid(Exception):
    """The VNF index either does not exist or is equal to zero"""
    pass


class InvalidTranscoderId(Exception):
    """Invalid transcoder ID in spectators payload"""
    pass


class VduUuidMissRedis(Exception):
    """ The redis does not include OSM data for the VDU uuid in redis, only the status 404 """
    pass


class VnfUuidMissRedis(Exception):
    """ The redis does not include OSM data for the VDU uuid in redis, only the status 404 """
    pass
