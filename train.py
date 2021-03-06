import torch
import torch.nn
import torch.optim
import torch.utils.data
import torchvision.models
import torchvision.transforms as transforms
from tensorboardX import SummaryWriter

import MobileNet
import MobileNetV2
import config

# use_cuda
use_cuda = config.use_cuda and torch.cuda.is_available()
# log
write = SummaryWriter(log_dir='log')

# load data
root = config.root
train_set = torchvision.datasets.CIFAR10(root=root, train=True, download=True,
                                         transform=transforms.Compose([
                                             transforms.RandomResizedCrop(224),
                                             transforms.RandomHorizontalFlip(),
                                             transforms.ToTensor(),
                                             transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                                                  std=[0.229, 0.224, 0.225])]),
                                         )
eval_set = torchvision.datasets.CIFAR10(root=root, train=False, download=True,
                                        transform=transforms.Compose([
                                            transforms.Resize(256),
                                            transforms.CenterCrop(224),
                                            transforms.ToTensor(),
                                            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                                                 std=[0.229, 0.224, 0.225])]),
                                        )
train_loader = torch.utils.data.DataLoader(dataset=train_set, batch_size=config.batch_size, shuffle=True,
                                           num_workers=config.workers, pin_memory=True)
eval_loader = torch.utils.data.DataLoader(dataset=eval_set, batch_size=config.batch_size, shuffle=True,
                                          num_workers=config.workers, pin_memory=True)

# create model
if config.model == 'MobileNet':
    model = MobileNet.MobileNet()
elif config.model == 'MobileNetV2':
    model = MobileNetV2.MobileNetV2()
else:
    print('selece currect model')
    exit(0)

if use_cuda:
    model = torch.nn.DataParallel(model.cuda())
# model.load_state_dict(torch.load(config.model + '.pt'))

# criterion and optimizer
criterion = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(params=model.parameters(), lr=config.learning_rate, momentum=config.momentum,
                            weight_decay=config.weight_decay)
scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer=optimizer, milestones=config.scheduler_step, gamma=0.1)

# train the network
for epoch in range(config.epochs):
    # adjust learning_rate
    scheduler.step()
    print(optimizer.param_groups[0]['lr'])

    # train
    running_loss = 0
    correct = 0
    total = 0
    model.train()
    for i, (input, target) in enumerate(train_loader):
        if use_cuda:
            input, target = input.cuda(), target.cuda()
        output = model(input)
        loss = criterion(output, target)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        _, predicted = torch.max(output, 1)
        total += target.size(0)
        correct += torch.sum(predicted == target).item()
        if i % config.frequency == config.frequency - 1:
            print('train {}/{}: {}/{}: loss={:.3f}'.format(epoch, config.epochs, i, len(train_loader),
                                                           running_loss / config.frequency))
            print('train {}/{}: {}/{}: accuracy={:.3f}%'.format(epoch, config.epochs, i, len(train_loader),
                                                                correct / total * 100))
            write.add_scalar('Train/loss', running_loss / config.frequency, epoch * len(train_loader) + i)
            write.add_scalar('Train/accu', correct / total, epoch * len(train_loader) + i)
            running_loss = 0
            correct = 0
            total = 0

    # eval
    model.eval()
    correct = 0
    total = 0
    for i, (input, target) in enumerate(eval_loader):
        if use_cuda:
            input, target = input.cuda(), target.cuda()
        output = model(input)
        _, predicted = torch.max(output, 1)
        total += target.size(0)
        correct += (predicted == target).sum().item()
    print('the accuracy of {}/{} epoch is {:.3f}%'.format(epoch, config.epochs, correct / total * 100))
    write.add_scalar('Eval/accu', correct / total, epoch)

    # save
    torch.save(model.state_dict(), config.model + '.pt')
write.close()
