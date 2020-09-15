import pandas as pd
import feather
import numpy as np
import os
import sys
import re
import math
import shutil
from scipy import interpolate
import pdb
import datetime
###################################################################################
# June 2020 - preprocess for MTL publication (Jared)
# Sept 2020 - cleaned up for repo construction (Jared)
###################################################################################
first_time = True
n_features = 7
# metadata = pd.read_feather("../../metadata/lake_metadata_2700plus.feather")
metadata = pd.read_feather("../../metadata/lake_metadata_baseJune2020.feather")
ids = metadata['site_id'].values


# ids = metadata['site_id'].values

# obs_df = pd.read_feather("../../data/raw/additional_lakes/temperature_obs.feather")
# ids = np.unique(obs_df['nhdhr_id'].values)
# matches = [re.search('nhdhr_(.*)', i) for i in ids]
# ids = [m.group(1) for m in matches]
enable_glm = True
ct = 0
# to_del = ['120018008', '120020307', '120020636', '32671150', '58125241', '120020800', '91598525']
# ids = np.setdiff1d(ids, to_del)
n_lakes = ids.shape[0]
#accumulation for averaging
# means_per_lake = np.zeros((n_lakes,8), dtype=np.float_)
# means_per_lake[:] = np.nan
# var_per_lake = np.zeros((n_lakes,8),dtype=np.float_)
# var_per_lake[:] = np.nan


# for lake_ind, name in enumerate(ids):
#     nid = 'nhdhr_' + name
#     # if nid == 'nhdhr_120018008' or nid == 'nhdhr_120020307' or nid == 'nhdhr_120020636' or nid == 'nhdhr_32671150' or nid =='nhdhr_58125241':
#     #     continue
#     print("(",lake_ind,"/",str(len(ids)),") ","pre ", name)
#     ############################################
#     #read/format meteorological data for numpy
#     #############################################
#     # meteo_dates = np.loadtxt('../../data/raw/sb_pgdl_data_release/meteo/nhdhr_'+name+'_meteo.csv', delimiter=',', dtype=np.string_ , usecols=2)[1:]
#     # print("first meteo date", meteo_dates[0])


#     # obs = pd.read_feather('../../data/raw/sb_pgdl_data_release/obs/nhdhr_'+name+'_obs.feather')
#     # obs['date2'] = pd.to_datetime(obs.date)
#     # obs.sort_values('date2', inplace=True)
#     # print("first obs date: ",obs['date2'].values[0])

#     # #lower/uppur cutoff indices (to match observations)

#     # start_date = []
#     # end_date = []
#     # try:
#     #     start_date = "{:%Y-%m-%d}".format(obs.values[0,1])
#     # except:
#     #     start_date = obs.values[0,1]
#     # try:
#     #     end_date = "{:%Y-%m-%d}".format(obs.values[-1,1])
#     # except:
#     #     end_date = obs.values[-1,1]
#     # lower_cutoff = np.where(meteo_dates == start_date)[0][0] #457
#     # if len(np.where(meteo_dates == end_date)[0]) < 1: 
#     #     print("observation beyond meteorological data! data will only be used up to the end of meteorological data")
#     #     upper_cutoff = meteo_dates.shape[0]
#     # else:
#     #     upper_cutoff = np.where(meteo_dates == end_date)[0][0]+1 #14233

#     # meteo_dates = meteo_dates[lower_cutoff:upper_cutoff]


#     # #read from file and filter dates
#     # meteo = np.genfromtxt('../../data/raw/sb_pgdl_data_release/meteo/nhdhr_'+name+'_meteo.csv', delimiter=',', usecols=(3,4,5,6,7,8,9), skip_header=1)
#     # meteo = meteo[lower_cutoff:upper_cutoff,:]
#     # means_per_lake[lake_ind,1:] = [meteo[:,a].mean() for a in range(n_features)]
#     # var_per_lake[lake_ind,1:] = [meteo[:,a].std() ** 2 for a in range(n_features)]

#     glm_temps = pd.read_csv('../../data/raw/sb_pgdl_data_release/predictions/pb0_nhdhr_'+name+'_temperatures.csv')
#     glm_temps = glm_temps.values[:]
#     n_total_dates = glm_temps.shape[0]

#     #define depths from glm file
#     n_depths = glm_temps.shape[1]-1 #minus date and ice flag
#     max_depth = 0.5*(n_depths-1)
#     depths = np.arange(0, max_depth+0.5, 0.5)
#     depths_mean = depths.mean()
#     depths_var = depths.std() ** 2
#     means_per_lake[lake_ind, 0] = depths_mean
#     var_per_lake[lake_ind, 0] = depths_var

# mean_feats = np.average(means_per_lake, axis=0)   
# std_feats = np.average(var_per_lake ** (.5), axis=0)   
# print("mean feats: ", repr(mean_feats))
# print("std feats: ", repr(std_feats))
# assert mean_feats.shape[0] == 8
# assert std_feats.shape[0] == 8
# assert not np.isnan(np.sum(mean_feats))
# assert not np.isnan(np.sum(std_feats))

# sys.exit()
mean_feats =[5.35588822, 1.67022467e+02, 2.92219247e+02, 6.82630486e+00, 7.36783045e+01, 4.79831775e+00, 1.84282192e-03, 2.29087107e-03]
std_feats = [3.23048181, 8.52233583e+01, 6.08592310e+01, 1.27621347e+01,1.29242034e+01, 1.69712815e+00, 5.58626647e-03, 1.27255570e-02]

# mean_feats = [5.39943134, 1.66547735e2, 2.91895336e2, 6.76191477, 7.37264141e1, 4.79885221e0, 1.83438590e-3, 2.29069199e-3]
# std_feats = [3.25563170, 8.53092316e1, 6.09606032e1, 1.27855354e1, 1.29500991e1, 1.69787946, 5.58071004e-3, 1.27507001e-2]


ct = 0
cont = False
for it_ct,nid in enumerate(ids): #for each new additional lake
    ct += 1
    name = str(nid)

    # if not name == '159101759' and not cont:
    #     continue
    # else:
    #     cont = True
    nid = '143418975'
    nid = 'nhdhr_' + str(nid)

    # if nid == 'nhdhr_120018008' or nid == 'nhdhr_120020307' or nid == 'nhdhr_120020636' or nid == 'nhdhr_32671150' or nid =='nhdhr_58125241':
    #     continue
    print(ct," starting ", name)
    # if os.path.exists("../../data/processed/lake_data/"+name+"/features_pt.npy") and os.path.exists("../../data/processed/lake_data/"+name+"/dates_pt"):
    #     print("ALREADY DONE")
        # sys.exit()
        


    #for each unique lake

    ############################################
    #read/format meteorological data for numpy
    #############################################
    # meteo_dates = np.loadtxt('../../data/raw/figure3/nhd_'+name+'_meteo.csv', delimiter=',', dtype=np.string_ , usecols=0)
    meteo_dates = np.loadtxt('../../data/raw/sb_pgdl_data_release/meteo/nhdhr_'+name+'_meteo.csv', delimiter=',', dtype=np.string_ , usecols=2, skiprows=1)
    meteo_dates = np.array([x.decode() for x in meteo_dates])
    meteo_dates_pt = np.loadtxt('../../data/raw/sb_pgdl_data_release/meteo/nhdhr_'+name+'_meteo.csv', delimiter=',', dtype=np.string_ , usecols=2, skiprows=1)
    meteo_dates_pt = np.array([x.decode() for x in meteo_dates_pt])
    glm_temps = pd.read_csv('../../data/raw/sb_pgdl_data_release/predictions/pb0_nhdhr_'+name+'_temperatures.csv').values[:]
    # glm_temps[:,-1] = np.array([x.decode() for x in glm_temps[:,-1]])
    glm_temps_pt = pd.read_csv('../../data/raw/sb_pgdl_data_release/predictions/pb0_nhdhr_'+name+'_temperatures.csv').values[:]


 
    if isinstance(glm_temps[0,0], str):
        tmp = glm_temps[:,0][:]
        tmp = np.reshape(tmp,(len(tmp),1))
        glm_temps = np.delete(glm_temps, 0, 1)[:]
        glm_temps_pt = np.delete(glm_temps_pt, 0, 1)[:]
        glm_temps = np.append(glm_temps, tmp, axis=1)
        glm_temps_pt = np.append(glm_temps_pt, tmp, axis=1)

    n_depths = glm_temps.shape[1]-1 #minus date 
    # print("n_depths: " + str(n_depths))
    max_depth = 0.5*(n_depths-1)
    depths = np.arange(0, max_depth+0.5, 0.5)
    # depths_normalized = np.divide(depths - depths.mean(), depths.std())
    depths_normalized = np.divide(depths - mean_feats[0], std_feats[0])

    ice_flags = pd.read_csv('../../data/raw/sb_pgdl_data_release/ice_flags/pb0_nhdhr_'+name+'_ice_flag.csv').values[:]
    ice_flags_pt = pd.read_csv('../../data/raw/sb_pgdl_data_release/ice_flags/pb0_nhdhr_'+name+'_ice_flag.csv').values[:]

    #lower/uppur cutoff indices (to match observations)
    obs = pd.read_feather('../../data/raw/sb_pgdl_data_release/obs/nhdhr_'+name+"_obs.feather")
    obs = obs[obs['depth'] <= max_depth] 
    obs.sort_values(by='date', axis=0, ascending=True, inplace=True, kind='quicksort', na_position='last', ignore_index=False)
    #sort observations
    start_date = obs.values[0,1]
    start_date_pt = glm_temps[0,-1]


    #do date offset for pre-pend meteo
    if pd.Timestamp(start_date) - pd.DateOffset(days=90) < pd.Timestamp(start_date_pt):
        start_date = str(pd.Timestamp(start_date) - pd.DateOffset(days=90))[:10]
    else:
        start_date = start_date_pt

    assert start_date_pt == ice_flags_pt[0,0]
    end_date = obs.values[-1,1]
    end_date_pt = "{:%Y-%m-%d}".format(pd.Timestamp(glm_temps[-1,-1]))


    #cut files to between first and last observation
    lower_cutoff = np.where(meteo_dates == start_date)[0][0] #457
    if len(np.where(meteo_dates == end_date)[0]) < 1: 
        print("observation beyond meteorological data! data will only be used up to the end of meteorological data")
        upper_cutoff = meteo_dates.shape[0]
    else:
        upper_cutoff = np.where(meteo_dates == end_date)[0][0]+1 #14233
    meteo_dates = meteo_dates[lower_cutoff:upper_cutoff]

   #cut files to between first and last GLM simulated date for pre-train data
    if len(np.where(meteo_dates_pt == start_date_pt)[0]) < 1: 
        print("observation beyond meteorological data! PRE-TRAIN data will only be starting at the start of meteorological data")
        start_date_pt = meteo_dates_pt[0]
    if len(np.where(meteo_dates_pt == end_date_pt)[0]) < 1: 
        print("observation beyond meteorological data! PRE-TRAIN data will only be used up to the end of meteorological data")
        end_date_pt = meteo_dates_pt[-1]
    lower_cutoff_pt = np.where(meteo_dates_pt == start_date_pt)[0][0] #457
    upper_cutoff_pt = np.where(meteo_dates_pt == end_date_pt)[0][0] #457
    meteo_dates_pt = meteo_dates_pt[lower_cutoff_pt:upper_cutoff_pt]
    


    



    #read from file and filter dates
    # meteo = np.genfromtxt('../../data/raw/figure3/nhd_'+name+'_meteo.csv', delimiter=',', usecols=(1,2,3,4,5,6,7))
    meteo = np.genfromtxt('../../data/raw/sb_pgdl_data_release/meteo/nhdhr_'+name+'_meteo.csv', delimiter=',', usecols=(3,4,5,6,7,8,9), skip_header=1)
    meteo_pt = np.genfromtxt('../../data/raw/sb_pgdl_data_release/meteo/nhdhr_'+name+'_meteo.csv', delimiter=',', usecols=(3,4,5,6,7,8,9), skip_header=1)
    meteo = meteo[lower_cutoff:upper_cutoff,:]
    meteo_pt = meteo_pt[lower_cutoff_pt:upper_cutoff_pt,:]

    #normalize data
    # meteo_means = [meteo[:,a].mean() for a in range(n_features)]
    # meteo_std = [meteo[:,a].std() for a in range(n_features)]
    # meteo_norm = (meteo - meteo_means[:]) / meteo_std[:]
    meteo_norm = (meteo - mean_feats[1:]) / std_feats[1:]
    meteo_norm_pt = (meteo_pt - mean_feats[1:]) / std_feats[1:]

    #meteo = final features sans depth
    #meteo_norm = normalized final features sans depth

    ################################################################################
    # read/format GLM temperatures and observation data for numpy
    ###################################################################################
    n_total_dates = glm_temps.shape[0]
    n_total_dates_pt = glm_temps_pt.shape[0]

    #define depths from glm file

    #cut glm temps to meteo dates for observation data PRETRAIN
    # glm_temps_pt[:,-1] = np.array([pd.Timestamp(glm_temps_pt[a,-1]).strftime('%Y-%m-%d') for a in range(n_total_dates_pt)]) 
    if len(np.where(glm_temps_pt[:,-1] == start_date_pt[0])) < 1:
        print("pretrain glm outputs begin at " + start_date_pt + "which is before GLM data which begins at " + glm_temps_pt[0,0])
        lower_cutoff_pt = 0
        new_meteo_lower_cutoff_pt = np.where(meteo_dates_pt == glm_temps_pt[0,-1])[0][0]
        meteo_pt = meteo_pt[new_meteo_lower_cutoff_pt:,:]
        meteo_norm_pt = meteo_norm_pt[new_meteo_lower_cutoff_pt:,:]
        meteo_dates_pt = meteo_dates_pt[new_meteo_lower_cutoff_pt:]
    else:
        lower_cutoff_pt = np.where(glm_temps_pt[:,-1] == start_date_pt)[0][0] 

    if len(np.where(glm_temps_pt[:,-1] == end_date_pt)[0]) < 1: 
        print("pretrain glm outputs extend to " + end_date_pt + "which is beyond GLM data which extends to " + glm_temps_pt[-1,-1])
        upper_cutoff_pt = glm_temps_pt[:,-1].shape[0]
        new_meteo_upper_cutoff_pt = np.where(meteo_dates_pt == glm_temps_pt[-1,-1])[0][0]
        meteo_pt = meteo_pt[:new_meteo_upper_cutoff_pt,:]
        meteo_norm_pt = meteo_norm_pt[:new_meteo_upper_cutoff_pt,:]
        meteo_dates_pt = meteo_dates_pt[:new_meteo_upper_cutoff_pt]
    else:
        upper_cutoff_pt = np.where(glm_temps_pt[:,-1] == end_date_pt)[0][0] 

    glm_temps_pt = glm_temps_pt[lower_cutoff_pt:upper_cutoff_pt,:]
    ice_flags_pt = ice_flags_pt[lower_cutoff_pt:upper_cutoff_pt,:]

    #cut glm temps to meteo dates for observation data
    # glm_temps[:,0] = np.array([pd.Timestamp(glm_temps[a,0]).strftime('%Y-%m-%d') for a in range(n_total_dates)]) 
    if len(np.where(glm_temps[:,-1] == start_date)[0]) < 1:
        print("observations begin at " + start_date + "which is before GLM data which begins at " + glm_temps[0,-1])
        lower_cutoff = 0
        new_meteo_lower_cutoff = np.where(meteo_dates == glm_temps[0,-1])[0][0]
        meteo = meteo[new_meteo_lower_cutoff:,:]
        meteo_norm = meteo_norm[new_meteo_lower_cutoff:,:]
        meteo_dates = meteo_dates[new_meteo_lower_cutoff:]
    else:
        lower_cutoff = np.where(glm_temps[:,-1] == start_date)[0][0] 

    if len(np.where(glm_temps[:,-1] == end_date)[0]) < 1: 
        print("observations extend to " + end_date + "which is beyond GLM data which extends to " + glm_temps[-1,-1])
        upper_cutoff = glm_temps[:,-1].shape[0]
        new_meteo_upper_cutoff = np.where(meteo_dates == glm_temps[-1,-1])[0][0] + 1
        meteo = meteo[:new_meteo_upper_cutoff,:]
        meteo_norm = meteo_norm[:new_meteo_upper_cutoff,:]
        meteo_dates = meteo_dates[:new_meteo_upper_cutoff]
    else:
        upper_cutoff = np.where(glm_temps[:,-1] == end_date)[0][0] +1

    glm_temps = glm_temps[lower_cutoff:upper_cutoff,:]
    ice_flags = ice_flags[lower_cutoff:upper_cutoff,:]
    n_dates_pt = glm_temps_pt.shape[0]
    n_dates = glm_temps.shape[0]
    # print("dates: ", n_dates, " , pretrain dates: ", n_dates_pt)

    if n_dates != meteo.shape[0]:
        raise Exception("dates dont match")
        print(n_dates)
        print(meteo.shape[0])
        sys.exit()

    assert n_dates == meteo.shape[0]
    assert n_dates_pt == meteo_pt.shape[0]
    assert n_dates == meteo_norm.shape[0]
    assert n_dates_pt == meteo_norm_pt.shape[0]
    assert n_dates == glm_temps.shape[0]
    assert n_dates_pt == glm_temps_pt.shape[0]
    #assert dates line up
    assert(glm_temps[0,-1] == meteo_dates[0])
    assert(glm_temps_pt[0,-1] == meteo_dates_pt[0])
    
    if glm_temps[-1,-1] != meteo_dates[-1]:
        print(glm_temps[-1,-1])
        print(meteo_dates[-1])
        raise Exception("dates dont match")
        sys.exit()
    
    if glm_temps_pt[-1,-1] != meteo_dates_pt[-1]:
        print(glm_temps_pt[-1,-1])
        print(meteo_dates_pt[-1])
        raise Exception("dates don't match")
        sys.exit()
    assert(glm_temps[-1,-1] == meteo_dates[-1])
    assert(glm_temps_pt[-1,-1] == meteo_dates_pt[-1])
    glm_temps = glm_temps[:,:-1]
    glm_temps_pt = glm_temps_pt[:,:-1]
    obs = obs.values[:,1:] #remove needless nhd column
    n_obs = obs.shape[0]

    # print("pretrain dates: ", start_date_pt, "->", end_date_pt)
    # print("train dates: ", start_date, "->", end_date)
    ############################################################
    #fill numpy matrices
    ##################################################################
    feat_mat_pt = np.empty((n_depths, n_dates_pt, n_features+2)) #[depth->7 meteo features-> ice flag]
    feat_mat_pt[:] = np.nan
    feat_norm_mat_pt = np.empty((n_depths, n_dates_pt, n_features+1)) #[standardized depth -> 7 std meteo features]
    feat_norm_mat_pt[:] = np.nan
    glm_mat_pt = np.empty((n_depths, n_dates_pt))
    glm_mat_pt[:] = np.nan


    feat_mat = np.empty((n_depths, n_dates, n_features+2)) #[depth->7 meteo features-> ice flag]
    feat_mat[:] = np.nan
    feat_norm_mat = np.empty((n_depths, n_dates, n_features+1)) #[standardized depth -> 7 std meteo features]
    feat_norm_mat[:] = np.nan
    glm_mat = np.empty((n_depths, n_dates))
    glm_mat[:] = np.nan
    obs_trn_mat = np.empty((n_depths, n_dates))
    obs_trn_mat[:] = np.nan
    obs_tst_mat = np.empty((n_depths, n_dates))
    obs_tst_mat[:] = np.nan
    # print("n depths: " + str(n_depths))
    for d in range(n_depths):
        #fill pretrain data
        feat_mat_pt[d,:,0] = depths[d] 
        feat_mat_pt[d,:,1:-1] = meteo_pt[:]
        feat_mat_pt[d,:,-1] = ice_flags_pt[:,1]        
        feat_norm_mat_pt[d,:,0] = depths_normalized[d]
        feat_norm_mat_pt[d,:,1:] = meteo_norm_pt[:]
        glm_mat_pt[d,:] = glm_temps_pt[:,d]

        #fill train data
        feat_mat[d,:,0] = depths[d] 
        feat_mat[d,:,1:-1] = meteo[:]
        feat_mat[d,:,-1] = ice_flags[:,1]        
        feat_norm_mat[d,:,0] = depths_normalized[d]
        feat_norm_mat[d,:,1:] = meteo_norm[:]
        glm_mat[d,:] = glm_temps[:,d]

    #verify all mats filled

    if np.isnan(np.sum(feat_mat)):
        raise Exception("ERROR: Preprocessing failed, there is missing data: features for training")
        sys.exit()
    if np.isnan(np.sum(feat_mat_pt)):
        raise Exception("ERROR: Preprocessing failed, there is missing data: features for pretraining ")
        sys.exit()
    if np.isnan(np.sum(feat_norm_mat)):
        raise Exception("ERROR: Preprocessing failed, there is missing data feat norm")
        sys.exit() 
    if np.isnan(np.sum(feat_norm_mat)):
        raise Exception("ERROR: Preprocessing failed, there is missing data feat norm")
        sys.exit() 
    if enable_glm:
        if np.isnan(np.sum(glm_mat)):
            # print("Warning: there is missing data in glm output")
            for i in range(n_depths):
                for t in range(n_dates):
                    if np.isnan(glm_mat[i,t]):
                        x = depths[i]
                        xp = depths[0:(i)]
                        yp = glm_mat[0:(i),t]
                        if xp.shape[0] == 1:
                            glm_mat[i,t] = glm_mat[i-1,t]
                        else:
                            f = interpolate.interp1d(xp, yp,  fill_value="extrapolate")
                            glm_mat[i,t] = f(x) #interp_temp

            assert not np.isnan(np.sum(glm_mat))
        if np.isnan(np.sum(glm_mat_pt)):
            # print("Warning: there is missing data in glm output")
            for i in range(n_depths):
                for t in range(n_dates_pt):
                    if np.isnan(glm_mat_pt[i,t]):
                        x = depths[i]
                        xp = depths[0:(i)]
                        yp = glm_mat_pt[0:(i),t]
                        if xp.shape[0] == 1:
                            glm_mat_pt[i,t] = glm_mat_pt[i-1,t]
                        else:
                            f = interpolate.interp1d(xp, yp,  fill_value="extrapolate")
                            glm_mat_pt[i,t] = f(x) #interp_temp

            assert not np.isnan(np.sum(glm_mat_pt))

    #observations, round to nearest 0.5m depth and put in train/test matrices
    # obs[:,1] = np.round((obs[:,1]*2).astype(np.float)) / 2  #round
    # print(depths)
    obs_g = 0
    obs_d = 0

    #get unique observation days
    unq_obs_dates = np.unique(obs[:,0])
    n_unq_obs_dates = unq_obs_dates.shape
    first_tst_date = obs[0,0]
    last_tst_date = obs[math.floor(obs.shape[0]/3),0]
    last_tst_obs_ind = np.where(obs[:,0] == last_tst_date)[0][-1]
    n_pretrain = meteo_dates_pt.shape[0]
    n_tst = last_tst_obs_ind + 1
    n_trn = obs.shape[0] - n_tst

    last_train_date = obs[-1,0]
    if last_tst_obs_ind + 1 >= obs.shape[0]:
        last_tst_obs_ind -= 1
    first_train_date = obs[last_tst_obs_ind + 1,0]
    first_pretrain_date = meteo_dates_pt[0]
    last_pretrain_date = meteo_dates_pt[-1]
    #test data
    n_tst_obs_placed = 0
    n_trn_obs_placed = 0
    for o in range(0,last_tst_obs_ind+1):
        #verify data in depth range
        if obs[o,1] > depths[-1]:
            obs_g += 1
            # print("observation depth " + str(obs[o,1]) + " is greater than the max depth of " + str(max_depth))
            continue
        if len(np.where(meteo_dates == obs[o,0])[0]) < 1:
            obs_d += 1
            continue
        if len(np.where(depths == np.round(obs[o,1]*2)/2)[0]) == 0:
            pdb.set_trace()
        depth_ind = np.where(depths == np.round(obs[o,1]*2)/2)[0][0]
        date_ind = np.where(meteo_dates == obs[o,0])[0][0]
        obs_tst_mat[depth_ind, date_ind] = obs[o,2]
        n_tst_obs_placed += 1

    #train data
    for o in range(last_tst_obs_ind+1, n_obs):
        if obs[o,1] > depths[-1]:
            obs_g += 1
            # print("observation depth " + str(obs[o,1]) + " is greater than the max depth of " + str(max_depth))
            continue
        depth_ind = np.where(depths == np.round(obs[o,1]*2)/2)[0][0]
        if len(np.where(meteo_dates == obs[o,0])[0]) < 1:
            obs_d += 1
            continue

        date_ind = np.where(meteo_dates == obs[o,0])[0][0]

        obs_trn_mat[depth_ind, date_ind] = obs[o,2]
        n_trn_obs_placed += 1


    d_str = ""
    if obs_d > 0:
        d_str = ", and "+str(obs_d) + " observations outside of combined date range of meteorological and GLM output"
    # if obs_g > 0 or obs_d > 0:
        # continue
    print("lake " + str(ct) + ",  id: " + name + ": " + str(obs_g) + "/" + str(n_obs) + " observations greater than max depth " + str(max_depth) + d_str)
    #write features and labels to processed data
    print("pre-training: ", first_pretrain_date, "->", last_pretrain_date, "(", n_pretrain, ")")
    print("training: ", first_train_date, "->", last_train_date, "(", n_trn, ")")
    print("testing: ", first_tst_date, "->", last_tst_date, "(", n_tst, ")")
    if not os.path.exists("../../data/processed/lake_data/"+name): 
        os.mkdir("../../data/processed/lake_data/"+name)
    if not os.path.exists("../../models/"+name):
        os.mkdir("../../models/"+name)
    feat_path_pt = "../../data/processed/lake_data/"+name+"/features_pt"
    feat_path = "../../data/processed/lake_data/"+name+"/features"
    norm_feat_path_pt = "../../data/processed/lake_data/"+name+"/processed_features_pt"
    norm_feat_path = "../../data/processed/lake_data/"+name+"/processed_features"
    glm_path_pt = "../../data/processed/lake_data/"+name+"/glm_pt"
    glm_path = "../../data/processed/lake_data/"+name+"/glm"
    trn_path = "../../data/processed/lake_data/"+name+"/train_b"
    tst_path = "../../data/processed/lake_data/"+name+"/test_b"
    full_path = "../../data/processed/lake_data/"+name+"/full"
    dates_path = "../../data/processed/lake_data/"+name+"/dates"
    dates_path_pt = "../../data/processed/lake_data/"+name+"/dates_pt"

    #geometry
    # shutil.copyfile('../../data/raw/figure3/nhd_'+name+'_geometry.csv', "../../data/processed/WRR_69Lake/"+name+"/geometry")

    np.save(feat_path, feat_mat)
    np.save(feat_path_pt, feat_mat_pt)
    np.save(norm_feat_path, feat_norm_mat)
    np.save(norm_feat_path_pt, feat_norm_mat_pt)
    np.save(glm_path, glm_mat)
    np.save(glm_path_pt, glm_mat_pt)
    np.save(dates_path, meteo_dates)
    np.save(dates_path_pt, meteo_dates_pt)
    np.save(trn_path, obs_trn_mat)
    np.save(tst_path, obs_tst_mat)
    full = obs_trn_mat
    full[np.nonzero(np.isfinite(obs_tst_mat))] = obs_tst_mat[np.isfinite(obs_tst_mat)]
    np.save(full_path, full)
    print("completed!")



