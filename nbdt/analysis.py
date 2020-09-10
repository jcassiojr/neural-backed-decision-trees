from nbdt.utils import set_np_printoptions
from nbdt.model import (
    SoftEmbeddedDecisionRules as SoftRules,
    HardEmbeddedDecisionRules as HardRules
)
from nbdt import metrics
import numpy as np


__all__ = names = (
    'Noop', 'ConfusionMatrix', 'ConfusionMatrixJointNodes',
    'IgnoredSamples', 'HardEmbeddedDecisionRules', 'SoftEmbeddedDecisionRules')
keys = ('path_graph', 'path_wnids', 'classes', 'dataset', 'accepts_metric')


def add_arguments(parser):
    pass


class Noop:

    accepts_classes = lambda trainset, **kwargs: trainset.classes

    def __init__(self, classes=()):
        set_np_printoptions()

        self.classes = classes
        self.num_classes = len(classes)
        self.epoch = None

    def start_epoch(self, epoch):
        self.epoch = epoch

    def start_train(self, epoch):
        assert epoch == self.epoch

    def update_batch(self, outputs, targets):
        pass

    def end_train(self, epoch):
        assert epoch == self.epoch

    def start_test(self, epoch):
        assert epoch == self.epoch

    def end_test(self, epoch):
        assert epoch == self.epoch

    def end_epoch(self, epoch):
        assert epoch == self.epoch


class ConfusionMatrix(Noop):

    def __init__(self, classes):
        super().__init__(classes)
        self.k = len(classes)
        self.m = None

    def start_train(self, epoch):
        super().start_train(epoch)
        raise NotImplementedError()

    def start_test(self, epoch):
        super().start_test(epoch)
        self.m = np.zeros((self.k, self.k))

    def update_batch(self, outputs, targets):
        super().update_batch(outputs, targets)
        _, predicted = outputs.max(1)
        if len(predicted.shape) == 1:
            predicted = predicted.numpy().ravel()
            targets = targets.numpy().ravel()
            ConfusionMatrix.update(self.m, predicted, targets)

    def end_test(self, epoch):
        super().end_test(epoch)
        recall = self.recall()
        for row, cls in zip(recall, self.classes):
            print(row, cls)
        print(recall.diagonal(), '(diagonal)')

    @staticmethod
    def update(confusion_matrix, preds, labels):
        preds = tuple(preds)
        labels = tuple(labels)

        for pred, label in zip(preds, labels):
            confusion_matrix[label, pred] += 1

    @staticmethod
    def normalize(confusion_matrix, axis):
        total = confusion_matrix.astype(np.float).sum(axis=axis)
        total = total[:, None] if axis == 1 else total[None]
        return confusion_matrix / total

    def recall(self):
        return ConfusionMatrix.normalize(self.m, 1)

    def precision(self):
        return ConfusionMatrix.normalize(self.m, 0)


class IgnoredSamples(Noop):
    """ Counter for number of ignored samples in decision tree """

    def __init__(self, classes=()):
        super().__init__(classes)
        self.ignored = None

    def start_test(self, epoch):
        super().start_test(epoch)
        self.ignored = 0

    def update_batch(self, outputs, targets):
        super().update_batch(outputs, targets)
        self.ignored += outputs[:,0].eq(-1).sum().item()
        return self.ignored

    def end_test(self, epoch):
        super().end_test(epoch)
        print("Ignored Samples: {}".format(self.ignored))


class DecisionRules(Noop):
    """Generic support for evaluating embedded decision rules."""

    accepts_dataset = lambda trainset, **kwargs: trainset.__class__.__name__
    accepts_path_graph = True
    accepts_path_wnids = True
    accepts_metric = True

    name = 'NBDT'

    def __init__(self, *args, Rules=HardRules, metric='top1', **kwargs):
        self.rules = Rules(*args, **kwargs)
        self.metric = getattr(metrics, metric)()

    def start_test(self, epoch):
        self.metric.clear()

    def update_batch(self, outputs, targets):
        super().update_batch(outputs, targets)
        outputs = self.rules.forward(outputs)
        self.metric.forward(outputs, targets)
        accuracy = round(self.metric.correct / float(self.metric.total), 4) * 100
        return accuracy

    def end_test(self, epoch):
        super().end_test(epoch)
        accuracy = round(self.metric.correct / self.metric.total * 100., 2)
        print(f'{self.name} Accuracy: {accuracy}%, {self.metric.correct}/{self.metric.total}')


class HardEmbeddedDecisionRules(DecisionRules):
    """Evaluation is hard."""

    name = 'NBDT-Hard'


class SoftEmbeddedDecisionRules(DecisionRules):
    """Evaluation is soft."""

    name = 'NBDT-Soft'

    def __init__(self, *args, Rules=None, **kwargs):
        super().__init__(*args, Rules=SoftRules, **kwargs)
