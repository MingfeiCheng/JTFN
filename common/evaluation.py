r""" Evaluate mask prediction """
import torch
import numpy as np

from skimage import morphology

def expand_pixels(mask, distance):
    """
    expand images with a fixed distance.
    Implemented in N(4)
    distance = |x - s| + |y - t|
    :param mask: original binary mask
    :param distance: expand mask with this distance
    :return: expanded binary mask
    """
    if distance <= 0:
        return mask
    expand_mask = copy.deepcopy(mask)
    h, w = np.where(mask > 0)
    for x, y in zip(h, w):
        expand_mask[x-distance:x+distance+1, y] = 1.0
        expand_mask[x, y-distance:y+distance+1] = 1.0
    return expand_mask
    
def computeF1(pred, gt):
    """

    :param pred: prediction, tensor
    :param gt: gt, tensor
    :return: segmentation metric
    """
    # 1, h, w
    tp = (gt * pred).sum().to(torch.float32)
    tn = ((1 - gt) * (1 - pred)).sum().to(torch.float32)
    fp = ((1 - gt) * pred).sum().to(torch.float32)
    fn = (gt * (1 - pred)).sum().to(torch.float32)

    epsilon = 1e-7

    precision = tp / (tp + fp + epsilon)
    recall = tp / (tp + fn + epsilon)

    f1_score = 2 * (precision * recall) / (precision + recall + epsilon)

    return f1_score * 100, precision * 100, recall * 100

def computeTopo(pred, gt):
    """
    :param pred: prediction, tensor
    :param gt: gt, tensor
    :return: Topo metric
    """
    pred = pred[0].detach().cpu().numpy().astype(int)  # float data does not support bit_and and bit_or
    gt = gt[0].detach().cpu().numpy().astype(int)

    pred = morphology.skeletonize(pred >= 0.5)
    gt = morphology.skeletonize(gt >= 0.5)

    # expand
    expand_pred = expand_pixels(pred, 2)
    expand_gt = expand_pixels(gt, 2)

    pred = pred.astype(int)
    gt = gt.astype(int)
    expand_pred = expand_pred.astype(int)
    expand_gt = expand_gt.astype(int)


    cor_intersection = expand_gt & pred # gt & pred

    com_intersection = gt & expand_pred # gt & pred

    cor_tp = np.sum(cor_intersection)
    com_tp = np.sum(com_intersection)

    sk_pred_sum = np.sum(pred)
    sk_gt_sum = np.sum(gt)

    smooth = 1e-7
    correctness = cor_tp / (sk_pred_sum + smooth)
    completeness = com_tp / (sk_gt_sum + smooth)

    quality = cor_tp / (sk_pred_sum + sk_gt_sum - com_tp + smooth)

    return torch.tensor(correctness * 100), torch.tensor(completeness * 100), torch.tensor(quality * 100)

class Evaluator:
    r""" Computes intersection and union between prediction and ground-truth """
    @classmethod
    def initialize(cls):
        cls.ignore_index = 255

    @classmethod
    def classify_prediction(cls, pred_mask, batch):
        # bs, 1, h, w
        gt_mask = batch.get('anno_mask')
        if 'ignore_mask' in batch.keys():
            ignore_mask = batch.get('ignore_mask') # 0 or 1, bs, 1, h, w
            gt_mask = gt_mask * ignore_mask
            pred_mask = pred_mask * ignore_mask

        f1 = []
        precision = []
        recall = []
        cor = []
        com = []
        quality = []
        for _pred_mask, _gt_mask in zip(pred_mask, gt_mask):
            f1_, precision_, recall_ = computeF1(_pred_mask, _gt_mask)
            cor_, com_, quality_ = computeTopo(_pred_mask, _gt_mask)
            f1.append(f1_)
            precision.append(precision_)
            recall.append(recall_)
            cor.append(cor_)
            com.append(com_)
            quality.append(quality_)
        f1 = torch.stack(f1) # bs, v
        # print('f1_score', f1.shape)
        # print(f1)
        precision = torch.stack(precision)
        recall = torch.stack(recall)
        cor = torch.stack(cor)
        com = torch.stack(com)
        quality = torch.stack(quality)
        return f1, precision, recall, quality, cor, com
