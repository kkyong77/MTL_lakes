#!/bin/bash -l
#PBS -l walltime=23:59:00,nodes=1:ppn=24:gpus=2,mem=16gb 
#PBS -m abe 
#PBS -N adfdf197-9f62-4650-8866-676709b89aee_pgml_sparse 
#PBS -o adfdf197-9f62-4650-8866-676709b89aee_pgml_sparse.stdout 
#PBS -q k40 

source takeme_source.sh

source activate mtl_env
python train_PGDL_custom_sparse.py adfdf197-9f62-4650-8866-676709b89aee