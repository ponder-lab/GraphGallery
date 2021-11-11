import torch
import torch.nn as nn
from torch import optim

from graphgallery.nn.models import TorchEngine
from graphgallery.nn.metrics.pytorch import Accuracy
from graphgallery.nn.layers.pytorch import activations


class Node2GridsCNN(TorchEngine):
    def __init__(self,
                 in_features,
                 out_features,
                 mapsize_a,
                 mapsize_b,
                 conv_channel=64,
                 hids=[200],
                 acts=['relu6'],
                 attnum=10,
                 dropout=0.6,
                 weight_decay=0.00015,
                 att_reg=0.07,
                 lr=0.008,
                 bias=True):

        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(
                in_channels=in_features,
                out_channels=conv_channel,
                kernel_size=(2, 1),
                stride=1,
                padding=0
            ),
            nn.Softmax(dim=1),
        )
        lin = []
        in_features = (mapsize_a - 1) * mapsize_b * conv_channel
        for hid, act in zip(hids, acts):
            lin.append(nn.Linear(in_features, hid, bias=bias))
            lin.append(activations.get(act))
            lin.append(nn.Dropout(dropout))
            in_features = hid
        lin.append(nn.Linear(in_features, out_features, bias=bias))

        self.lin = nn.Sequential(*lin)
        self.attention = nn.Parameter(torch.ones(attnum, mapsize_a - 1, mapsize_b))
        self.att_reg = att_reg
        self.compile(loss=nn.CrossEntropyLoss(),
                     optimizer=optim.RMSprop(self.parameters(),
                                             weight_decay=weight_decay, lr=lr),
                     metrics=[Accuracy()])

    def forward(self, x):
        attention = torch.sum(self.attention, dim=0) / self.attention.size(0)
        x = self.conv(x)
        x = attention * x + x
        x = x.view(x.size(0), -1)
        out = self.lin(x)
        return out

    def compute_loss(self, output_dict, y):
        pred = output_dict['pred']
        loss = self.loss(pred, y)
        if self.training:
            attention = self.attention.view(-1)
            loss += self.att_reg * torch.sum(attention ** 2)
        return loss

    def loss_backward(self, loss):
        # here I exactly follow the author's implementation in
        # <https://github.com/Ray-inthebox/Node2Gridss>
        # But what is it????
        loss.backward(loss)