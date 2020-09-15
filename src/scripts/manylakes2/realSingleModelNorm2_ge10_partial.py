from __future__ import print_function
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.clip_grad import clip_grad_norm_
from torch.nn.init import xavier_normal_
from datetime import date
import pandas as pd
import pdb
import random
import math
import sys
import os
sys.path.append('../../data')
sys.path.append('../../models')
sys.path.append('/home/invyz/workspace/Research/lake_monitoring/src/data')
# from data_operations import calculatePhysicalLossDensityDepth
from pytorch_data_operations import buildLakeDataForRNNPretrain, calculate_energy,calculate_ec_loss_manylakes, transformTempToDensity, calculate_dc_loss
from pytorch_model_operations import saveModel
import pytorch_data_operations
from io_operations import makeLabels, averageTrialsToFinalOutputFullData, saveFeatherFullDataWithEnergy
import datetime
#multiple dataloader wrapping?
import pdb
import torchvision
from torch.utils.data import DataLoader
from torchvision import transforms
from pytorch_data_operations import buildLakeDataForRNN_manylakes_finetune2, parseMatricesFromSeqs, preprocessForTargetLake
#script start
currentDT = datetime.datetime.now()
print(str(currentDT))
####################################################3
#  pretrain script, takes lakename as required command line argument
###################################################33

#enable/disable cuda 
use_gpu = True 
torch.backends.cudnn.benchmark = True
torch.set_printoptions(precision=10)

#collect command line args
# target_id = "1102086"
# lakes = ['2723871', '1099432', '1101504']

# target_id = "1097324"
# lakes = ['2723765', '1101942', '1099432'] 
# target_id = "13293262"
# lakes = ['120052351', '9022741', '1101942']

# #collect command line args

#experiment flags
unsup_target_lake_only_flag = True
normalize_features_to_target_lake_flag = False


#preprocess if needed
# preprocessForTargetLake(target_id, addDirRemove=1)

#find similar lakes
# lakes = getSimilarLakes(target_id, method='geotemp')
lakes = [sys.argv[1]]








# target_id = "2723871"
# lakes = ["1102086" ,"1101504", "1099432"] #2723871
n_lakes = len(lakes)

# target_bool = False
# target_id = None
# if target_bool:
#     target_id = target_id







### debug tools
debug_train = False
debug_end = False
verbose = False
pretrain = True
save = True
save_pretrain = True

unsup_loss_cutoff = 40
dc_unsup_loss_cutoff = 1e-3
dc_unsup_loss_cutoff2 = 1e-2
#############################################################
#training loop
####################################################################
n_hidden = 20 #fixed
train_epochs = 10000
pretrain_epochs = 10000
# train_epochs = 1
# pretrain_epochs = 1

#####################3
#params
###########################33
n_ep = pretrain_epochs  #number of epochs
if debug_train or debug_end:
    n_ep = 10
first_save_epoch = 0
patience = 100

#ow
seq_length = 350 #how long of sequences to use in model
begin_loss_ind = 0#index in sequence where we begin to calculate error or predict
n_features = 8  #number of physical drivers
win_shift = 175 #how much to slide the window on training set each time
save = True 

lake_ind = -1
for lakename in lakes:
    lake_ind += 1
    print("lake "+str(lake_ind)+": "+lakename)
    data_dir = "../../data/processed/lake_data/"+lakename+"/"

    ###############################
    # data preprocess
    ##################################
    #create train and test sets
    (trn_data, all_data, all_phys_data, all_dates,
    hypsography) = buildLakeDataForRNNPretrain(lakename, data_dir, seq_length, n_features,
                                       win_shift= win_shift, begin_loss_ind=begin_loss_ind,
                                       excludeTest=False, normAll=False, normGE10=False)

    n_depths = torch.unique(all_data[:,:,0]).size()[0]
    # if verbose:
        # print("n depths: ", n_depths)

    ####################
    #model params
    ########################

    batch_size =trn_data.size()[0]
    yhat_batch_size = n_depths*1
    grad_clip = 1.0 #how much to clip the gradient 2-norm in training
    lambda1 = 0.0001#magnitude hyperparameter of l1 loss
    ec_lambda = 0.2 #magnitude hyperparameter of ec loss
    ec_threshold = 36 #anything above this far off of energy budget closing is penalized
    dc_lambda = 10. #magnitude hyperparameter of depth-density constraint (dc) loss
    ul = False

    #Dataset classes
    class TemperatureTrainDataset(Dataset):
        #training dataset class, allows Dataloader to load both input/target
        def __init__(self, trn_data):
            # depth_data = depth_trn
            self.len = trn_data.shape[0]
            # assert data.shape[0] ==trn_data depth_data.shape[0]
            self.x_data = trn_data[:,:,:-1].float()
            # self.x_depth = depth_data.float()
            self.y_data = trn_data[:,:,-1].float()

        def __getitem__(self, index):
            return self.x_data[index], self.y_data[index]

        def __len__(self):
            return self.len

    class TotalModelOutputDataset(Dataset):
        #dataset for unsupervised input(in this case all the data)
        def __init__(self, all_data, all_phys_data, all_dates):
            #data of all model output, and corresponding unstandardized physical quantities
            #needed to calculate physical loss
            self.len = all_data.shape[0]
            self.data = all_data[:,:,:-1].float()
            self.label = all_data[:,:,-1].float() #DO NOT USE IN MODEL, FOR DEBUGGING
            self.phys = all_phys_data[:,:,:].float()
            helper = np.vectorize(lambda x: date.toordinal(pd.Timestamp(x).to_pydatetime()))
            dates = helper(all_dates)
            self.dates = dates

        def __getitem__(self, index):
            return self.data[index], self.phys[index], self.dates[index], self.label[index]

        def __len__(self):
            return self.len

    #format training data for loading
    train_data = TemperatureTrainDataset(trn_data)

    #get depth area percent data
    depth_areas = torch.from_numpy(hypsography).float().flatten()

    if use_gpu:
        depth_areas = depth_areas.cuda()

    #format total y-hat data for loading
    total_data = TotalModelOutputDataset(all_data, all_phys_data, all_dates)
    n_batches = math.floor(trn_data.size()[0] / batch_size)

    assert yhat_batch_size == n_depths

    #batch samplers used to draw samples in dataloaders
    batch_sampler = pytorch_data_operations.ContiguousBatchSampler(batch_size, n_batches)


    #method to calculate l1 norm of model
    def calculate_l1_loss(model):
        def l1_loss(x):
            return torch.abs(x).sum()

        to_regularize = []
        # for name, p in model.named_parameters():
        for name, p in model.named_parameters():
            if 'bias' in name:
                continue
            else:
                #take absolute value of weights and sum
                to_regularize.append(p.view(-1))
        l1_loss_val = torch.tensor(1, requires_grad=True, dtype=torch.float32)
        l1_loss_val = l1_loss(torch.cat(to_regularize))
        return l1_loss_val


    #lstm class
    class myLSTM_Net(nn.Module):
        def __init__(self, input_size, hidden_size, batch_size):
            super(myLSTM_Net, self).__init__()
            self.input_size = input_size
            self.hidden_size = hidden_size
            self.batch_size = batch_size
            self.lstm = nn.LSTM(input_size = n_features, hidden_size=hidden_size, batch_first=True) 
            self.out = nn.Linear(hidden_size, 1)
            self.hidden = self.init_hidden()
            # self.w_upper_to_lower = []
            # self.w_lower_to_upper = []           
            # if ul:
            #     self.w_upper_to_lower = torch.nn.Parameter(xavier_normal_(torch.empty(n_depths-1, self.hidden_size)))
            #     self.w_lower_to_upper = torch.nn.Parameter(xavier_normal_(torch.empty(n_depths-1, self.hidden_size)))

        def init_hidden(self, batch_size=0):
            # initialize both hidden layers
            if batch_size == 0:
                batch_size = self.batch_size
            ret = (xavier_normal_(torch.empty(1, batch_size, self.hidden_size)),
                    xavier_normal_(torch.empty(1, batch_size, self.hidden_size)))
            if use_gpu:
                item0 = ret[0].cuda(non_blocking=True)
                item1 = ret[1].cuda(non_blocking=True)
                ret = (item0,item1)
            return ret
        
        def forward(self, x, hidden):
            depth_sets = []
            if ul:
                depth_sets = int(x.size()[0]/n_depths)

            self.lstm.flatten_parameters()
            x = x.float()
            x, hidden = self.lstm(x, self.hidden)
            self.hidden = hidden
            # temp_zero = []
            # temp_zero2 = []
            # x_upper = []
            # x_lower = []
            # w_upper_to_lower = []
            # w_lower_to_upper = []
            # if ul:
            #     temp_zero = torch.zeros(1, seq_length, self.hidden_size)
            #     temp_zero2 = torch.zeros(1, self.hidden_size)
            #     if use_gpu:
            #         temp_zero = temp_zero.cuda()
            #         temp_zero2 = temp_zero2.cuda()
            #     x_upper = torch.cat((temp_zero, x[:-1]))
            #     x_lower = torch.cat((x[1:], temp_zero))

            #     #shift and repeat for each date such that the weighted combination is computed correctly
            #     w_upper_to_lower = torch.cat((temp_zero2, self.w_upper_to_lower)).repeat(depth_sets,1)
            #     w_upper_to_lower = w_upper_to_lower.view(w_upper_to_lower.size()[0], 1, w_upper_to_lower.size()[1]).repeat(1,seq_length,1)
            #     w_lower_to_upper = torch.cat((self.w_lower_to_upper, temp_zero2)).repeat(depth_sets,1)
            #     w_lower_to_upper = w_lower_to_upper.view(w_lower_to_upper.size()[0], 1, w_lower_to_upper.size()[1]).repeat(1,seq_length,1)


            #     x = x + x_upper*w_upper_to_lower + x_lower*w_lower_to_upper
            # # sys.exit()
            x = self.out(x)
            return x, hidden


    lstm_net = myLSTM_Net(n_features, n_hidden, batch_size)

    if use_gpu:
        lstm_net = lstm_net.cuda(0)

    #define training loss function and optimizer
    mse_criterion = nn.MSELoss()
    optimizer = optim.Adam(lstm_net.parameters(), lr=.005)#, weight_decay=0.01)

    #paths to save
    if not os.path.exists("../../../models/single_lake_models/"+lakename):
        os.mkdir("../../../models/single_lake_models/"+lakename)
    save_path = "../../../models/single_lake_models/"+lakename+"/pretrain_experiment_normAllGr10_partial"

    min_loss = 99999
    min_mse_tsterr = None
    ep_min_mse = -1
    epoch_since_best = 0

    manualSeed = [random.randint(1, 99999999) for i in range(n_ep)]

    #convergence variables
    eps_converged = 0
    eps_till_converge = 10
    converged = False
    if pretrain:
        for epoch in range(n_ep):
            if verbose:
                print("pretrain epoch: ", epoch)
            torch.manual_seed(manualSeed[epoch])
            if use_gpu:
                torch.cuda.manual_seed_all(manualSeed[epoch])
            running_loss = 0.0

            #reload loader for shuffle
            #batch samplers used to draw samples in dataloaders
            batch_sampler = pytorch_data_operations.ContiguousBatchSampler(batch_size, n_batches)
            batch_sampler_all = pytorch_data_operations.RandomContiguousBatchSampler(all_data.size()[0], seq_length, yhat_batch_size, n_batches)
            alldataloader = DataLoader(total_data, batch_sampler=batch_sampler_all, pin_memory=True)
            trainloader = DataLoader(train_data, batch_sampler=batch_sampler, pin_memory=True)
            multi_loader = pytorch_data_operations.MultiLoader([trainloader, alldataloader])


            #zero the parameter gradients
            optimizer.zero_grad()
            avg_loss = 0
            avg_unsup_loss = 0
            avg_dc_unsup_loss = 0

            batches_done = 0
            for i, batches in enumerate(multi_loader):
                #load data
                inputs = None
                targets = None
                depths = None
                unsup_inputs = None
                unsup_phys_data = None
                unsup_depths = None
                unsup_dates = None
                unsup_labels = None
                for j, b in enumerate(batches):
                    if j == 0:
                        inputs, targets = b
                    if j == 1:
                        unsup_inputs, unsup_phys_data, unsup_dates, unsup_labels = b



                #cuda commands
                if(use_gpu):
                    inputs = inputs.cuda()
                    targets = targets.cuda()

                #forward  prop
                lstm_net.hidden = lstm_net.init_hidden(batch_size=inputs.size()[0])
                h_state = None
                inputs = inputs.float()
                outputs, h_state = lstm_net(inputs, h_state)
                outputs = outputs.view(outputs.size()[0],-1)

                loss_outputs = outputs[:,begin_loss_ind:]
                loss_targets = targets[:,begin_loss_ind:]

                #unsupervised output
                h_state = None
                h_state2 = None
                lstm_net.hidden = lstm_net.init_hidden(batch_size = yhat_batch_size)
                unsup_loss = torch.tensor(0).float()
                if use_gpu:
                    loss_outputs = loss_outputs.cuda()
                    loss_targets = loss_targets.cuda()
                    unsup_inputs = unsup_inputs.cuda()
                    unsup_phys_data = unsup_phys_data.cuda()
                    unsup_labels = unsup_labels.cuda()
                    unsup_dates = unsup_dates.cuda()
                    unsup_loss = unsup_loss.cuda()

                unsup_outputs, h_state = lstm_net(unsup_inputs, h_state)

                if ec_lambda > 0: #if we are calculating energy loss
                    unsup_loss = calculate_ec_loss_manylakes(unsup_inputs[:,begin_loss_ind:,:],
                                               unsup_outputs[:,begin_loss_ind:,:],
                                               unsup_phys_data[:,begin_loss_ind:,:],
                                               unsup_labels[:,begin_loss_ind:],
                                               unsup_dates[:,begin_loss_ind:],                                        
                                               depth_areas,
                                               n_depths,
                                               ec_threshold,
                                               use_gpu, 
                                               combine_days=1)

                dc_unsup_loss = torch.tensor(0).float()
                if use_gpu:
                    dc_unsup_loss = dc_unsup_loss.cuda()

                if dc_lambda > 0:
                    dc_unsup_loss = calculate_dc_loss(unsup_outputs, n_depths, use_gpu)
            

                #calculate losses
                reg1_loss = 0
                if lambda1 > 0:
                    reg1_loss = calculate_l1_loss(lstm_net)

                loss = mse_criterion(loss_outputs, loss_targets) + lambda1*reg1_loss + ec_lambda*unsup_loss + dc_lambda*dc_unsup_loss


                avg_loss += loss
                avg_unsup_loss += unsup_loss
                avg_dc_unsup_loss += dc_unsup_loss

                batches_done += 1
                #backward prop
                loss.backward(retain_graph=False)
                if grad_clip > 0:
                    clip_grad_norm_(lstm_net.parameters(), grad_clip, norm_type=2)

                #optimize
                optimizer.step()

                #zero the parameter gradients
                optimizer.zero_grad()

                #print statistics
                running_loss += loss.item()
                if verbose:
                    if i % 3 == 2:
                        print('[%d, %5d] loss: %.3f' %
                             (epoch + 1, i + 1, running_loss / 3))
                        running_loss = 0.0
            avg_loss = avg_loss / batches_done

            # import pdb
            # pdb.set_trace()
            if avg_loss < min_loss:
                if epoch+1 > first_save_epoch:
                        #save model if best
                        if save_pretrain:
                            if verbose:
                                print("saved at", save_path)
                            saveModel(lstm_net.state_dict(), optimizer.state_dict(), save_path)

                        epoch_since_best = 0
                min_loss = avg_loss
                ep_min_mse = epoch +1
                epoch_since_best += 1
                    #check for convergence
            avg_unsup_loss = avg_unsup_loss / batches_done
            avg_dc_unsup_loss = avg_dc_unsup_loss / batches_done
            if verbose:
                print("dc loss=",avg_dc_unsup_loss)
                print("energy loss=",avg_unsup_loss)
                print("rmse loss=", avg_loss)
                print("min loss=", min_loss)
            if avg_loss < 1:
                if verbose:
                    print("training converged")
                converged = True
            if avg_unsup_loss < unsup_loss_cutoff:
                eps_converged +=1
                if verbose:
                    print("energy converged",eps_converged)
            else:
                eps_converged = 0

            if not avg_dc_unsup_loss < dc_unsup_loss_cutoff:
                converged = False
            else:
                if verbose:
                    print("depth consistency converged")
            if converged and eps_converged >= 10:
                print("pretraining finished in " + str(epoch) +" epochs")

                break

            # print("Epoch with min loss: ", ep_min_mse, " -> loss=", min_loss, "with mse=", min_mse_tsterr)

            if epoch_since_best == patience:
                print("pretraining finished in " + str(epoch) +" epochs")
                continue
                # sys.exit()        
         



    #####################################################################################
    ####################################################3
    # fine tune
    ###################################################33
    ##########################################################################################33

    #####################
    #params
    ###########################
    n_ep = train_epochs  #number of epochs
    if debug_end:
        n_ep = 10
    first_save_epoch = 0
    patience = 1000
    epoch_since_best = 0
    ec_lambda = .01
    dc_lambda = 1.
    lambda1 = 0
    win_shift = 175 #how much to slide the window on training set each time
    data_dir = "../../data/processed/lake_data/"+lakename+"/"
    
    #paths to save

    pretrain_path = "../../../models/single_lake_models/"+lakename+"/pretrain_experiment_normAllGr10_partial"
    save_path = "../../../models/single_lake_models/"+lakename+"/PGRNN_basic_normAllGr10_partial"

    #arg for normalization of input features to that of the target lake 
    target_lake_arg = None
    if normalize_features_to_target_lake_flag:
        target_lake_arg = target_id
    
    ###############################
    # data preprocess
    ##################################
    #create train and test sets
    (trn_data, trn_dates, tst_data, tst_dates, unique_tst_dates, all_data, all_phys_data, all_dates,
    hypsography) = buildLakeDataForRNN_manylakes_finetune2(lakename, data_dir, seq_length, n_features,
                                       win_shift = win_shift, begin_loss_ind = begin_loss_ind, 
                                       latter_third_test=True, outputFullTestMatrix=False, 
                                       sparseTen=False, realization='none', allTestSeq=False, oldFeat=False, normGE10=True) 
    n_depths = torch.unique(all_data[:,:,0]).size()[0]
    u_depths = np.unique(tst_data[:,0,0])
    n_test_dates = unique_tst_dates.shape[0]


    # trn_data 
    batch_size = trn_data.size()[0]
    # batch_size = n_depths



    #Dataset classes
    class TemperatureTrainDataset(Dataset):
        #training dataset class, allows Dataloader to load both input/target
        def __init__(self, trn_data):
            # depth_data = depth_trn
            self.len = trn_data.shape[0]
            self.x_data = trn_data[:,:,:-1].float()
            self.y_data = trn_data[:,:,-1].float()

        def __getitem__(self, index):
            return self.x_data[index], self.y_data[index]

        def __len__(self):
            return self.len

    class TotalModelOutputDataset(Dataset):
        #dataset for unsupervised input(in this case all the data)
        def __init__(self, all_data, all_phys_data,all_dates):
            #data of all model output, and corresponding unstandardized physical quantities
            #needed to calculate physical loss
            self.len = all_data.shape[0]
            self.data = all_data[:,:,:-1].float()
            self.label = all_data[:,:,-1].float() #DO NOT USE IN MODEL
            self.phys = all_phys_data.float()
            helper = np.vectorize(lambda x: date.toordinal(pd.Timestamp(x).to_pydatetime()))
            dates = helper(all_dates)
            self.dates = dates

        def __getitem__(self, index):
            return self.data[index], self.phys[index], self.dates[index], self.label[index]

        def __len__(self):
            return self.len




    #format training data for loading
    train_data = TemperatureTrainDataset(trn_data)

    #get depth area percent data
    depth_areas = torch.from_numpy(hypsography).float().flatten()
    if use_gpu:
        depth_areas = depth_areas.cuda()

    #format total y-hat data for loading
    total_data = TotalModelOutputDataset(all_data, all_phys_data, all_dates)
    n_batches = math.floor(trn_data.size()[0] / batch_size)
    yhat_batch_size = n_depths

    #batch samplers used to draw samples in dataloaders
    batch_sampler = pytorch_data_operations.ContiguousBatchSampler(batch_size, n_batches)



    #load val/test data into enumerator based on batch size
    testloader = torch.utils.data.DataLoader(tst_data, batch_size=tst_data.size()[0], shuffle=False, pin_memory=True)



    #define LSTM model class
    class myLSTM_Net(nn.Module):
        def __init__(self, input_size, hidden_size, batch_size):
            super(myLSTM_Net, self).__init__()
            self.input_size = input_size
            self.hidden_size = hidden_size
            self.batch_size = batch_size
            self.lstm = nn.LSTM(input_size = n_features, hidden_size=hidden_size, batch_first=True) #batch_first=True?
            self.out = nn.Linear(hidden_size, 1) #1?
            self.hidden = self.init_hidden()
            self.w_upper_to_lower = []
            self.w_lower_to_upper = []
            # if ul:
            #     self.w_upper_to_lower = torch.nn.Parameter(xavier_normal_(torch.empty(n_depths-1, self.hidden_size)))
            #     self.w_lower_to_upper = torch.nn.Parameter(xavier_normal_(torch.empty(n_depths-1, self.hidden_size)))

        def init_hidden(self, batch_size=0):
            # initialize both hidden layers
            if batch_size == 0:
                batch_size = self.batch_size
            ret = (xavier_normal_(torch.empty(1, batch_size, self.hidden_size)),
                    xavier_normal_(torch.empty(1, batch_size, self.hidden_size)))
            if use_gpu:
                item0 = ret[0].cuda(non_blocking=True)
                item1 = ret[1].cuda(non_blocking=True)
                ret = (item0,item1)
            return ret
        
        def forward(self, x, hidden):
            depth_sets = []
            if ul:
                depth_sets = int(x.size()[0]/n_depths)

            self.lstm.flatten_parameters()
            x = x.float()
            x, hidden = self.lstm(x, self.hidden)
            self.hidden = hidden
            # temp_zero = []
            # temp_zero2 = []
            # x_upper = []
            # x_lower = []
            # w_upper_to_lower = []
            # w_lower_to_upper = []
            # if ul:
            #     temp_zero = torch.zeros(1, seq_length, self.hidden_size)
            #     temp_zero2 = torch.zeros(1, self.hidden_size)
            #     if use_gpu:
            #         temp_zero = temp_zero.cuda()
            #         temp_zero2 = temp_zero2.cuda()
            #     x_upper = torch.cat((temp_zero, x[:-1]))
            #     x_lower = torch.cat((x[1:], temp_zero))

            #     #shift and repeat for each date such that the weighted combination is computed correctly
            #     w_upper_to_lower = torch.cat((temp_zero2, self.w_upper_to_lower)).repeat(depth_sets,1)
            #     w_upper_to_lower = w_upper_to_lower.view(w_upper_to_lower.size()[0], 1, w_upper_to_lower.size()[1]).repeat(1,seq_length,1)
            #     w_lower_to_upper = torch.cat((self.w_lower_to_upper, temp_zero2)).repeat(depth_sets,1)
            #     w_lower_to_upper = w_lower_to_upper.view(w_lower_to_upper.size()[0], 1, w_lower_to_upper.size()[1]).repeat(1,seq_length,1)


            #     x = x + x_upper*w_upper_to_lower + x_lower*w_lower_to_upper
            # sys.exit()
            x = self.out(x)
            return x, hidden

    #method to calculate l1 norm of model
    def calculate_l1_loss(model):
        def l1_loss(x):
            return torch.abs(x).sum()

        to_regularize = []
        # for name, p in model.named_parameters():
        for name, p in model.named_parameters():
            if 'bias' in name:
                continue
            else:
                #take absolute value of weights and sum
                to_regularize.append(p.view(-1))
        l1_loss_val = torch.tensor(1, requires_grad=True, dtype=torch.float32)
        l1_loss_val = l1_loss(torch.cat(to_regularize))
        return l1_loss_val


    lstm_net = myLSTM_Net(n_features, n_hidden, batch_size)

    pretrain_dict = torch.load(pretrain_path)['state_dict']
    model_dict = lstm_net.state_dict()
    pretrain_dict = {k: v for k, v in pretrain_dict.items() if k in model_dict}
    model_dict.update(pretrain_dict)
    lstm_net.load_state_dict(pretrain_dict)

    #tell model to use GPU if needed
    if use_gpu:
        lstm_net = lstm_net.cuda()




    #define loss and optimizer
    mse_criterion = nn.MSELoss()
    optimizer = optim.Adam(lstm_net.parameters(), lr=.005)#, weight_decay=0.01)

    #training loop

    min_mse = 99999
    min_mse_tsterr = None
    ep_min_mse = -1
    best_pred_mat = np.empty(())
    manualSeed = [random.randint(1, 99999999) for i in range(n_ep)]






    #convergence variables
    eps_converged = 0
    eps_till_converge = 10
    converged = False

    for epoch in range(n_ep):
        if verbose:
            print("train epoch: ", epoch)
        if use_gpu:
            torch.cuda.manual_seed_all(manualSeed[epoch])
        running_loss = 0.0

        #reload loader for shuffle
        #batch samplers used to draw samples in dataloaders
        batch_sampler = pytorch_data_operations.ContiguousBatchSampler(batch_size, n_batches)
        batch_sampler_all = pytorch_data_operations.RandomContiguousBatchSampler(all_data.size()[0], seq_length, yhat_batch_size, n_batches)

        alldataloader = DataLoader(total_data, batch_sampler=batch_sampler_all, pin_memory=True)
        trainloader = DataLoader(train_data, batch_sampler=batch_sampler, pin_memory=True)
        multi_loader = pytorch_data_operations.MultiLoader([trainloader, alldataloader])


        #zero the parameter gradients
        optimizer.zero_grad()
        lstm_net.train(True)
        avg_loss = 0
        avg_unsup_loss = 0
        avg_dc_unsup_loss = 0
        batches_done = 0
        for i, batches in enumerate(multi_loader):
            #load data
            inputs = None
            targets = None
            depths = None
            unsup_inputs = None
            unsup_phys_data = None
            unsup_depths = None
            unsup_dates = None
            unsup_labels = None
            for j, b in enumerate(batches):
                if j == 0:
                    inputs, targets = b

                if j == 1:
                    unsup_inputs, unsup_phys_data, unsup_dates, unsup_labels = b

            #cuda commands
            if(use_gpu):
                inputs = inputs.cuda()
                targets = targets.cuda()

            #forward  prop
            lstm_net.hidden = lstm_net.init_hidden(batch_size=inputs.size()[0])
            h_state = None
            outputs, h_state = lstm_net(inputs, h_state)
            outputs = outputs.view(outputs.size()[0],-1)

            #unsupervised output
            h_state = None
            lstm_net.hidden = lstm_net.init_hidden(batch_size = yhat_batch_size)
            unsup_loss = torch.tensor(0).float()
            if use_gpu:
                unsup_inputs = unsup_inputs.cuda()
                unsup_phys_data = unsup_phys_data.cuda()
                unsup_labels = unsup_labels.cuda()
                depth_areas = depth_areas.cuda()
                unsup_dates = unsup_dates.cuda()
                unsup_loss = unsup_loss.cuda()
            
            #get unsupervised outputs
            unsup_outputs, h_state = lstm_net(unsup_inputs, h_state)


            #calculate unsupervised loss
            if ec_lambda > 0:
                unsup_loss = calculate_ec_loss_manylakes(unsup_inputs[:,begin_loss_ind:,:],
                                           unsup_outputs[:,begin_loss_ind:,:],
                                           unsup_phys_data[:,begin_loss_ind:,:],
                                           unsup_labels[:,begin_loss_ind:],
                                           unsup_dates[:,begin_loss_ind:],                                        
                                           depth_areas,
                                           n_depths,
                                           ec_threshold,
                                           use_gpu, 
                                           combine_days=1)
            dc_unsup_loss = torch.tensor(0).float()
            if use_gpu:
                dc_unsup_loss = dc_unsup_loss.cuda()

            if dc_lambda > 0:
                dc_unsup_loss = calculate_dc_loss(unsup_outputs, n_depths, use_gpu)
        

            #calculate losses
            reg1_loss = 0
            if lambda1 > 0:
                reg1_loss = calculate_l1_loss(lstm_net)


            loss_outputs = outputs[:,begin_loss_ind:]
            loss_targets = targets[:,begin_loss_ind:].cpu()


            #get indices to calculate loss
            loss_indices = np.array(np.isfinite(loss_targets.cpu()), dtype='bool_')
            # if ~np.isfinite(loss_targets).any():
            #     print("loss targets should not be nan shouldnt happen")
            #     sys.exit()
            if use_gpu:
                loss_outputs = loss_outputs.cuda()
                loss_targets = loss_targets.cuda()
            loss = mse_criterion(loss_outputs[loss_indices], loss_targets[loss_indices]) + lambda1*reg1_loss + ec_lambda*unsup_loss + dc_lambda*dc_unsup_loss
            #backward

            loss.backward(retain_graph=False)
            if grad_clip > 0:
                clip_grad_norm_(lstm_net.parameters(), grad_clip, norm_type=2)

            #optimize
            optimizer.step()

            #zero the parameter gradients
            optimizer.zero_grad()
            avg_loss += loss
            avg_unsup_loss += unsup_loss
            avg_dc_unsup_loss += dc_unsup_loss
            batches_done += 1

        #check for convergence
        avg_loss = avg_loss / batches_done
        avg_unsup_loss = avg_unsup_loss / batches_done
        avg_dc_unsup_loss = avg_dc_unsup_loss / batches_done
        if verbose:
            print("dc loss=",avg_dc_unsup_loss)
            print("energy loss=",avg_unsup_loss)
            print("rmse loss=", avg_loss)

        if avg_loss < 1:
            if verbose:
                print("training converged")
            converged = True
        if avg_unsup_loss < unsup_loss_cutoff:
            eps_converged += 1
            if verbose:
                print("energy converged",eps_converged)
            else:
                throwaway = 0
        else:
            eps_converged = 0

        if not avg_dc_unsup_loss < dc_unsup_loss_cutoff2:
            converged = False
        else:
            if verbose:
                print("depth consistency converged")
        if converged and eps_converged >= 10:
            saveModel(lstm_net.state_dict(), optimizer.state_dict(), save_path)
            print("training finished in ", epoch)
            break
    print("TRAINING COMPLETE")
    saveModel(lstm_net.state_dict(), optimizer.state_dict(), save_path)

    with torch.no_grad():

        avg_mse = 0
        ct = 0
        for i, data in enumerate(testloader, 0):
            #now for mendota data
            #this loop is dated, there is now only one item in testloader

            #parse data into inputs and targets
            inputs = data[:,:,:n_features].float()
            targets = data[:,:,-1].float()
            targets = targets[:, begin_loss_ind:]
            tmp_dates = tst_dates[:, begin_loss_ind:]
            depths = inputs[:,:,0]

            if use_gpu:
                inputs = inputs.cuda()
                targets = targets.cuda()

            #run model
            h_state = None
            lstm_net.hidden = lstm_net.init_hidden(batch_size=inputs.size()[0])
            pred, h_state = lstm_net(inputs, h_state)
            pred = pred.view(pred.size()[0],-1)
            pred = pred[:, begin_loss_ind:]

            #calculate error
            loss_indices = np.array(np.isfinite(targets.cpu()), dtype='bool_')
            inputs = inputs[:, begin_loss_ind:, :]
            depths = depths[:, begin_loss_ind:]
            mse = mse_criterion(pred[loss_indices], targets[loss_indices])
            # print("test loss = ",mse)
            avg_mse += mse

            if mse > 0: #obsolete i think
                ct += 1
            avg_mse = avg_mse / ct

            
            #save model 
            (outputm_npy, labelm_npy) = parseMatricesFromSeqs(pred.cpu(), targets.cpu(), depths, tmp_dates, n_depths, 
                                                            n_test_dates, u_depths,
                                                            unique_tst_dates) 
            loss_output = outputm_npy[~np.isnan(labelm_npy)]
            loss_label = labelm_npy[~np.isnan(labelm_npy)]
            mat_rmse = np.sqrt(((loss_output - loss_label) ** 2).mean())
            print(mat_rmse)

            print("RMSE=", str(mat_rmse))