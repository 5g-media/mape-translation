from translator.basemetric import BaseMetric


class Metric(BaseMetric):
    def __init__(self, raw_metric):
        self.raw_metric = raw_metric
        super().__init__()

    def get_data_model(self):
        pass