import abc


class BaseMetric(abc.ABC):
    """Abstract operations of passive monitoring metrics"""


    def source(self):
        """"""
        pass

    def get_data_model(self):
        pass
