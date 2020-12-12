#!/bin/bash
#SBATCH -n 1
#SBATCH -N 1
#SBATCH -p regular
#SBATCH --mem=16G
#SBATCH -t 0-20:00
#SBATCH --job-name=NoSZ_rlz_70-79
#SBATCH -C haswell
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=namikawa@slac.stanford.edu
source ~/.bashrc.ext
py4so
python tmp_job_run_NoSZ_rlz_70-79.py
