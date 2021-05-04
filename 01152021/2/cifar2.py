'''Train CIFAR with PyTorch.

e.g.
    python3 cifar.py --netName=old-resnet50 --cifar=10 --bs=128
'''
from __future__ import print_function

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch.backends.cudnn as cudnn

import torchvision
import torchvision.transforms as transforms

import os
import argparse

#from models import *
import models as models
from utils import *

model_names = sorted(name for name in models.__dict__
    if not name.startswith("__")
    and callable(models.__dict__[name]))
# print(model_names)

# os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
# os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3,4,5,6,7"
parser = argparse.ArgumentParser(description='PyTorch CIFAR10 Training')
parser.add_argument('--lr', default=0.1, type=float, help='learning rate')
parser.add_argument('--resume', '-r',default=False, action='store_true', help='resume from checkpoint')
parser.add_argument('--netName', default='old_resnet18', choices=model_names, type=str, help='choosing network')
parser.add_argument('--bs', default=256, type=int, help='batch size')
parser.add_argument('--workers', default=8, type=int, help='workers')
parser.add_argument('--es', default=50, type=int, help='epoch size')
parser.add_argument('--cifar', default=10, type=int, help='dataset classes number')
args = parser.parse_args()

if not os.path.isdir('checkpoint/cifar'+str(args.cifar)+"/"+args.netName):
    os.makedirs('checkpoint/cifar'+str(args.cifar)+"/"+args.netName)

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(device)
best_acc = 0  # best test accuracy
start_epoch = 0  # start from epoch 0 or last checkpoint epoch


# Data
print('==> Preparing data..')
transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

if args.cifar ==100:
    trainset = torchvision.datasets.CIFAR100(root='./data', train=True, download=True, transform=transform_train)
else:
    args.cifar=10
    trainset = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=transform_train)
trainloader = torch.utils.data.DataLoader(trainset, batch_size=args.bs, shuffle=True, num_workers=args.workers)

if args.cifar ==100:
    testset = torchvision.datasets.CIFAR100(root='./data', train=False, download=True, transform=transform_test)
else:
    testset = torchvision.datasets.CIFAR10(root='./data', train=False, download=True, transform=transform_test)
testloader = torch.utils.data.DataLoader(testset, batch_size=args.bs, shuffle=False, num_workers=args.workers)



# Model
print('==> Building model..')
try:
    net = models.__dict__[args.netName](num_classes=args.cifar)
except:
    net = models.__dict__[args.netName]()

net = net.to(device)

if device == 'cuda':
    net = torch.nn.DataParallel(net)
    cudnn.benchmark = True

if args.resume:
    # Load checkpoint.
    print('==> Resuming from checkpoint..')
    # assert os.path.isdir('checkpoint'), 'Error: no checkpoint directory found!'
    checkpoint_path = './checkpoint/cifar'+str(args.cifar)+"/"+args.netName+"/model_best.t7"
    checkpoint = torch.load(checkpoint_path)
    net.load_state_dict(checkpoint['net'])
    best_acc = checkpoint['acc']
    print("BEST_ACCURACY: "+str(best_acc))
    start_epoch = checkpoint['epoch']

criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=0.9, weight_decay=5e-4)


# Training
def train(epoch):
    adjust_learning_rate(optimizer, epoch, args.lr, step=30)
    print('\nEpoch: %d   Learning rate: %f' % (epoch+1, optimizer.param_groups[0]['lr']))
    net.train()
    train_loss = 0
    correct = 0
    total = 0

    for batch_idx, (inputs, targets) in enumerate(trainloader):
        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = net(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        train_loss += loss.item()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()

        progress_bar(batch_idx, len(trainloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
            % (train_loss/(batch_idx+1), 100.*correct/total, correct, total))

    # file_path='records/cifar_' + str(args.cifar) + '_' +args.netName+'_train.txt'
    # record_str=str(epoch)+'\t'+"%.3f"%(train_loss/(batch_idx+1))+'\t'+"%.3f"%(100.*correct/total)+'\n'
    # write_record(file_path,record_str)
    return  [train_loss/(batch_idx+1), 100.*correct/total]


def test(epoch):
    global best_acc
    net.eval()
    test_loss = 0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch_idx, (inputs, targets) in enumerate(testloader):
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = net(inputs)
            loss = criterion(outputs, targets)

            test_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

            progress_bar(batch_idx, len(testloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
                % (test_loss/(batch_idx+1), 100.*correct/total, correct, total))

    file_path = 'records/cifar_' + str(args.cifar) + '_' +args.netName+ '_test.txt'
    record_str = str(epoch) + '\t' + "%.3f" % (test_loss / (batch_idx + 1)) + '\t' + "%.3f" % (
                100. * correct / total) + '\n'
    write_record(file_path, record_str)

    # Save checkpoint.
    acc = 100.*correct/total
    if acc > best_acc:
        print('Saving..')
        state = {
            'net': net.state_dict(),
            'acc': acc,
            'epoch': epoch,
        }
        save_path = './checkpoint/cifar'+str(args.cifar)+"/"+args.netName+"/model_best.t7"
        torch.save(state, save_path)
        best_acc = acc

    return [(test_loss / (batch_idx + 1)), (100. * correct / total)]

logfile = './checkpoint/cifar'+str(args.cifar)+"/"+args.netName+"/log.txt"
if not os.path.exists(logfile):
    record_str = "Epoch"+'\t'+"Train loss" +'\t'+"Test loss" +'\t'+"Train Acc"+ '\t'+"Test Acc"+'\n'
    write_record(logfile, record_str)

for epoch in range(start_epoch, start_epoch+args.es):
    train_loss, train_acc = train(epoch)
    test_loss, test_acc = test(epoch)
    record_str = str(epoch+1) + '\t' + "%.3f"%(train_loss) + '\t' \
                 + "%.3f"%(test_loss)+'\t'+"%.3f"%(train_acc)+'\t'+"%.3f"%(test_acc)+'\n'
    write_record(logfile, record_str)


