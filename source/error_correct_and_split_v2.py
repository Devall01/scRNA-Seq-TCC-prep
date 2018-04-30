
# coding: utf-8

# In[1]:


import os
import sys

json_path=os.path.abspath(sys.argv[1])
if not os.path.isfile(json_path):
    print("ERROR: Please provide path to a valid config.json file...")
    print(sys.argv[1])
    exit(1)

    
workpath, jsonfile = os.path.split(json_path)
os.chdir(workpath)


# In[2]:


import numpy as np
from itertools import islice
import math
import random
from collections import Counter
import matplotlib as mpl
import gzip, time, gc
from multiprocessing import Pool
from os import listdir
from os.path import isfile, join

import pickle
import linecache as ln


# In[3]:


#Read config.json file
import json
# use abspath from argv
with open(json_path) as json_file:
    parameter = json.load(json_file)

from os import listdir
from os.path import isfile, join
import re


# In[4]:


FASTQ_DIRS=parameter["FASTQ_DIRS"]
SAMPLE_NAMES=parameter['sample_names']


# In[5]:


barcode_filenames_per_sample = []
barcode_dirs_per_sample = []
read_filenames_per_sample = []
read_dirs_per_sample = []
for i_S in range(len(SAMPLE_NAMES)):
    barcode_filenames = []
    barcode_dirs = []
    read_filenames = []
    read_dirs = []
    for i_F in range(len(FASTQ_DIRS)):
        for f in sorted(listdir(str(FASTQ_DIRS[i_F]))):
            
            if (isfile(join(str(FASTQ_DIRS[i_F]), f)) and f.startswith(str(SAMPLE_NAMES[i_S])) and 
                f[-8:]=='fastq.gz' and f.find('R1')>0):
                
                barcode_filenames.append(f)
                barcode_dirs.append(str(FASTQ_DIRS[i_F])+f)
                
            if (isfile(join(str(FASTQ_DIRS[i_F]), f)) and f.startswith(str(SAMPLE_NAMES[i_S])) and 
                f[-8:]=='fastq.gz' and f.find('R2')>0):
                
                read_filenames.append(f)
                read_dirs.append(str(FASTQ_DIRS[i_F])+f)
                
#            pattern = r"^"+str(SAMPLE_NAMES[i_S])+"_S\d+_L00\d_([IR]\d)_001.fastq.gz"
#            match = re.match(pattern, f)
#            if match:
#                barcode_name = match.group(1)
#            if isfile(join(str(FASTQ_DIRS[i_F]), f)) and f.startswith(str(SAMPLE_NAMES[i_S])) and barcode_name == 'R1':
#                barcode_filenames.append(f)
#                barcode_dirs.append(str(FASTQ_DIRS[i_F])+f)
#            if isfile(join(str(FASTQ_DIRS[i_F]), f)) and f.startswith(str(SAMPLE_NAMES[i_S])) and barcode_name == 'R2':
#                read_filenames.append(f)
#                read_dirs.append(str(FASTQ_DIRS[i_F])+f)
    barcode_filenames_per_sample += [barcode_filenames]
    barcode_dirs_per_sample += [barcode_dirs]
    read_filenames_per_sample += [read_filenames]
    read_dirs_per_sample +=[read_dirs]
                
#print("BARCODE FILES(R1):")
#for i in range(len(barcode_dirs_per_sample)):
#    print("\nsample: "+SAMPLE_NAMES[i])
#    for j in range(len(barcode_dirs_per_sample[i])):
#        print(" "+barcode_dirs_per_sample[i][j])
        
#print("\n----------------------------------------------------------------------------------------")
#print("READ FILES(R2):")
#for i in range(len(read_dirs_per_sample)):
#    print("\nsample: "+SAMPLE_NAMES[i])
#    for j in range(len(read_dirs_per_sample[i])):
#        print(" "+read_dirs_per_sample[i][j])



# In[6]:
print("\n\n___________________ERROR_CORRECT_AND_SPLIT___________________")

BARCODE_LENGTH=parameter['BARCODE_LENGTH']
UMI_LENGTH=parameter['UMI_LENGTH']
output_dir = parameter['OUTPUT_DIR']
NUM_THREADS = parameter['NUM_THREADS']


# In[7]:


def encoding_map(ch):
    if ch=='A':return 0
    if ch=='G':return 1
    if ch=='C':return 2
    if ch=='T':return 3
    if ch=='N':return random.randint(0,3)

decoding_lst = ['A', 'G', 'C', 'T']

def encode(k):
    code = 0
    for ch in k:
        code *= 4
        code += encoding_map(ch)
    return code

def decode(code):
    ret = ''
    for _ in range(BARCODE_LENGTH):
        index = code & 3
        code >>= 2
        ret = decoding_lst[index] + ret
    return ret


# In[8]:


# ### Error-correct barcodes

from itertools import chain, combinations, product
def hamming_circle(s, n, alphabet='ATCG'):
    """Generate strings over alphabet whose Hamming distance from s is
    exactly n.
    """
    for positions in combinations(range(len(s)), n):
        for replacements in product(range(len(alphabet) - 1), repeat=n):
            cousin = list(s)
            for p, r in zip(positions, replacements):
                if cousin[p] == alphabet[r]:
                    cousin[p] = alphabet[-1]
                else:
                    cousin[p] = alphabet[r]
            yield encode(''.join(cousin))


def merge_barcodes(barcs):
    offset=barcs[0]
    barcs=barcs[1]
    retvec=[]
    for idd in range(len(codewords)):
        retvec+=[[]]
    for idx, barcode in enumerate(barcs):
        if barcode in codeword_set: retvec[cw[barcode]] +=[idx+offset]
        else:
            if barcode in brc_to_correct_neigbors:
                neighbors = hamming_circle(decode(barcode),1)
                for neighbor in neighbors:
                    if neighbor in brc_to_correct: retvec[cw[neighbor]] +=[idx+offset]; break;
    return retvec


# In[9]:


#LOAD barcodes
save_dir=str(parameter["SAVE_DIR"])
for i_S in range(len(SAMPLE_NAMES)):
    print( "Loading Barcodes for "+SAMPLE_NAMES[i_S]+'...',flush=True)
    t0 = time.time()
    with open(save_dir+SAMPLE_NAMES[i_S]+"_barcodes.dat", 'rb') as f:
        barcodes=pickle.load(f)

    with open(save_dir+SAMPLE_NAMES[i_S]+"_codewords.dat", 'rb') as f:
        codewords=pickle.load(f)

    with open(save_dir+SAMPLE_NAMES[i_S]+"_brc_idx_to_correct.dat", 'rb') as f:
        brc_idx_to_correct= pickle.load(f)
    
    t1 = time.time()
    print(t1-t0, "sec")
    
    #####################################
    
    chunksize=1+int(len(barcodes)/NUM_THREADS)
    
    cw={}
    for id in range(len(codewords)):
        cw[codewords[id]] = id

    barcode_split=[]
    for i in range(0, len(barcodes), chunksize):
        barcode_split+=[[i,barcodes[i:i+chunksize]]]

    print("Merging barcodes for "+SAMPLE_NAMES[i_S]+'...',flush=True)
    sys.stdout.flush()
    codeword_set = set(codewords)
    codeword_list = list(codewords)
    brc_to_correct=set(codewords[brc_idx_to_correct])
    
    #### Generate the set of all dist-1 neighbors of brc_to_correct (for fast check in merge func)
    #### note: the number of barcodes in this set is len(brc_to_correct)*3*barcode_length
    brc_to_correct_neigbors=set()
    for brc in brc_to_correct:
        neighbors = hamming_circle(decode(brc),1)
        for neighbor in neighbors:
            brc_to_correct_neigbors.add(neighbor)

    p = Pool(NUM_THREADS)
    t0 = time.time()
    ret_threads=p.map(merge_barcodes, barcode_split)
    p.close(); p.join()
    
    ret_vec=[]
    for idd in range(len(codewords)):
        idx_list=[]
        for t in range(len(ret_threads)):
            idx_list+=ret_threads[t][idd]
        ret_vec+=[idx_list]

    t1 = time.time()
    print(t1-t0, "sec")

    reads_per_barcode=[]
    for i in range(len(codewords)):
        reads_per_barcode+=[len(ret_vec[i])]

    print("NUM_OF_READS_in_CELL_BARCODES (after error-correct):",sum(reads_per_barcode))
    
    
    ####################################
    
    #temporary file to extract all reads
    all_reads_file = str(parameter["SAVE_DIR"])+'all_reads.fastq'
    all_reads_file_umi = str(parameter["SAVE_DIR"])+'all_umi.fastq'

    #create output directory
    import os
    if not os.path.isdir(output_dir):
        try:
            os.mkdir(output_dir)
        except OSError as e:
            print("OSError({0}): {1}".format(e.errno, e.strerror))

    barcode_dirs = barcode_dirs_per_sample[i_S] if len(SAMPLE_NAMES)>1 else barcode_dirs_per_sample[0]
    read_dirs = read_dirs_per_sample[i_S] if len(SAMPLE_NAMES)>1 else read_dirs_per_sample[0]

    #concatenate all .gz umi files
    print("Concatenating Files...",flush=True)
    sys.stdout.flush()
    def parallel_cat(inputvec):

        outfile=inputvec[0][0]
        dirs=inputvec[1][0]
        command = "cat "
        for files in dirs:
            command+=files+' '
        command+="> "+outfile+".gz"
        os.system(command)


    conc_params=[ [[all_reads_file_umi],[barcode_dirs]],[[all_reads_file],[read_dirs]]]
    p=Pool(2)
    t0 = time.time()
    p.map(parallel_cat, conc_params)
    t1 = time.time()
    print(t1-t0, "sec")
    p.close(); p.join()



    n_files=30
    tot=len(barcodes)*4
    li=int(np.divide(tot,n_files)-np.mod(np.divide(tot,n_files),4)+4)
    #print(str(li))



    # temporarilly unzip all reads
    print("temporarilly unzipping all_read files...",flush=True)
    sys.stdout.flush()
    def parallel_zcat_split(file):    
        os.chdir(str(parameter["SAVE_DIR"]))
        os.system('zcat '+file+'.gz | split -l '+str(li)+' --numeric-suffixes - '+file.split('/')[-1]+'_')
    p=Pool(2)
    t0 = time.time()
    p.map(parallel_zcat_split, [all_reads_file_umi,all_reads_file])
    os.chdir(workpath)
    t1 = time.time()
    print(t1-t0, "sec")
    p.close(); p.join()   
    
    os.system("rm "+all_reads_file_umi+'.gz')
    os.system("rm "+all_reads_file+'.gz')
    
    ALL_reads_file = [all_reads_file+'_%02.d' %  i for i in range(n_files)]
    ALL_reads_file_umi = [all_reads_file_umi+'_%02.d' %  i for i in range(n_files)]

    
    
    # Split single-cell files and umis ( using linecache.getline() )

    t0=time.time()
    for fi in range(n_files):
        hi,lo=((fi+1)*li/4,fi*li/4)
        if fi>0: append_write = 'a' # append if already exists
        else:append_write = 'w' # make a new file if not   

        for cell in range(len(codewords)):
            filename = SAMPLE_NAMES[i_S]+"_cell_"+str(cell).zfill(4)+'_'+decode(codewords[cell])
            print("writing " + filename +' part-'+str(fi)+"...\033[K",end='\r',flush=True)
            output_umis=""
            output_fastq=""
    #         output_check=""
    #         output_check_seq = ""
            for i in [j for j in ret_vec[cell] if (j<hi and j>=lo)]:
                adjusted_4i=np.mod(4*i,li)
                for l in range(1,5):
                    output_fastq+=ln.getline(ALL_reads_file[fi],adjusted_4i+l)
    #             temp1=ln.getline(ALL_reads_file_umi[fi],adjusted_4i+2)
    #             output_umis+=temp1[BARCODE_LENGTH:BARCODE_LENGTH+UMI_LENGTH]+"\n"
                output_umis+=ln.getline(ALL_reads_file_umi[fi],adjusted_4i+2)[BARCODE_LENGTH:BARCODE_LENGTH+UMI_LENGTH]+"\n"




    #             temp=ln.getline(ALL_reads_file[fi],adjusted_4i+1)
    #             output_check_seq=temp
    #             output_check=ln.getline(ALL_reads_file_umi[fi],adjusted_4i+1)
    #             if output_check_seq.split(' ')[0] == output_check.split(' ')[0]:
    #                 output_fastq+=temp
    #                 for l in range(2,5):
    #                     output_fastq+=ln.getline(ALL_reads_file[fi],adjusted_4i+l)
    #                 temp1=ln.getline(ALL_reads_file_umi[fi],adjusted_4i+2)
    #                 output_umis+=temp1[BARCODE_LENGTH:BARCODE_LENGTH+UMI_LENGTH]+"\n"



            sys.stdout.flush()
            with open(output_dir+filename+".umi", append_write) as umi:
                umi.write(output_umis)
            with open(output_dir+filename+".fastq", append_write) as reads:
                reads.write(output_fastq)
        ln.clearcache()

    print('')


    t1=time.time()
    print( t1-t0, "sec")



    #remove temp all_reads file
    os.system("rm -r "+' '.join(ALL_reads_file))
    os.system("rm -r "+' '.join(ALL_reads_file_umi))
    ln.clearcache()
    print("------------------ finished error_correct_and_split for "+SAMPLE_NAMES[i_S])
    
    
    
print("Successfully completed error_correct_and_split for all samples.\n")



# In[10]:


#compress output files
from os import listdir
from os.path import isfile, join
fastqfiles = [output_dir+f for f in listdir(output_dir) if isfile(join(output_dir, f)) and f[-6:]==".fastq"]

def gzip_fastqs(filepath):
    if filepath[-6:]==".fastq":
        os.system("gzip -f "+ filepath)

print("Compressing output with gzip...",flush=True)
sys.stdout.flush()

p=Pool(NUM_THREADS)
t0 = time.time()
p.map(gzip_fastqs, fastqfiles)
t1 = time.time()
print(t1-t0, "sec")
p.close(); p.join()


# In[11]:


#create batch file: singlecell_umi_read_list.txt

fastqfiles = [output_dir+f for f in sorted(listdir(output_dir)) if isfile(join(output_dir, f)) and f[-9:]==".fastq.gz"]
umifiles = [output_dir+f for f in sorted(listdir(output_dir)) if isfile(join(output_dir, f)) and f[-4:]==".umi"]
cell_ids = [f[:len(f)-4] for f in sorted(listdir(output_dir)) if isfile(join(output_dir, f)) and f[-4:]==".umi"]

out_data=''
for i in range(len(cell_ids)):
    out_data+=cell_ids[i]+'\t'+umifiles[i]+'\t'+fastqfiles[i]+'\n'

with open(str(parameter["OUTPUT_DIR"])+"umi_read_list.txt", 'w') as f:
                   f.write(out_data)
print("DONE")




