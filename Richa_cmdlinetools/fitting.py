import pickle
import sys, os, argparse
import ase.io as ase_io
import numpy as np
import tqdm
import json
import math
from nice.blocks import *
from nice.utilities import *

def main():
    """
    Command-line utility to compute NICE features. Training and testing is done here. We need the following from the user:
    1. The database file. 
    2. The name for final output file.
    2. Index for training commands for ase.io.read commands.
    3. number of environments to fit nice transfomers
    4. I will define the grid. 
    5. Input for HYPERS parameters required from user. Keeping 'gaussian_sigma_type': 'Constant','cutoff_smooth_width': 0.3, and 'radial_basis': 'GTO'
    6. Input for standardblocks- 
        Covariants: num_expand: Number of the most important input pairs to be considered for expansion.
                    max_take: Number of features to be considered for purification step. The default value is None.
                    n_components: Number of components for the PCA step. Default value None takes number of components equal to the number of covariants for each individual lambda.
        Invariants: num_expand: Number of the most important input pairs to be considered for expansion.
                    max_take: Number of features to be considered for purification step. The default value is None.
                    n_components: Number of components for the PCA step. Default value None takes number of components equal to the number of covariants for each individual lambda.
                    
    """
    #Tweak the autogenerated help output to look nicer (Keeping it same from previous file.)
        
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=22)
    parser = argparse.ArgumentParser(description=main.__doc__, formatter_class=formatter)
    #parser = argparse.ArgumentParser(description='Trial- to check where the main.__doc__ is', formatter_class=formatter)
    parser.add_argument('input', type=str, default="", nargs="?", help='XYZ file to load')
    parser.add_argument('-o', '--output', type=str, default="", help='Output files prefix. Defaults to input filename with stripped extension')
    parser.add_argument('-w','--which_output', type=int, default=1, help='1 for getting a different NICE for each species or else a single NICE for all species')
    parser.add_argument('--train_subset', type=str, default="0:10000", help='Index for reading the file for training in ASE format')
    #parser.add_argument('--test_subset', type=str, default="10000:15000", help='Index for reading the file for testing in ASE format')
    parser.add_argument('--environments_for_fitting', type=int, default=1000, help='Number of environments for fitting')
    parser.add_argument('--interaction_cutoff', type=int, default=6.3, help='Interaction cut-off')
    parser.add_argument('--max_radial', type=int, default=5, help='Number of radial channels')
    parser.add_argument('--max_angular', type=int, default=5, help='Number of angular momentum channels')
    parser.add_argument('--gaussian_sigma_constant', type=int, default=6.3, help='Gaussian smearing')
    parser.add_argument('--numexpcov', type=int, default=150, help='Number of the most important input pairs to be considered for expansion.')
    parser.add_argument('--numexpinv', type=int, default=300, help='Number of the most important input pairs to be considered for expansion.')
    parser.add_argument('--maxtakecov', type=int, default=None, help='Number of features to be considered for purification step.')
    parser.add_argument('--maxtakeinv', type=int, default=None, help='Number of features to be considered for purification step.')
    parser.add_argument('--ncompcov', type=int, default=None, help='Number of components for the PCA step.')
    parser.add_argument('--ncompinv', type=int, default=None, help='Number of components for the PCA step.')
    parser.add_argument('--json', type=str, default='{}', help='Additional hypers, as JSON string')
    
    
    #parser.add_argument('--select', type=str, default=":", help='Selection of input frames. ASE format.')
    #parser.add_argument('--nice', type=str, default="nice.pickle", help='Definition of the NICE contraction. Output from optimize_nice.py')
    #parser.add_argument('--blocks', type=int, default=1, help='Number of blocks to break the calculation into.')
    
    args = parser.parse_args()
    
    #File inputs
    filename = args.input
    output   = args.output
    whichoutput = args.which_output
    #select   = args.select    
    #nice     = args.nice
    #nblocks  = args.blocks
    
        
    #filename = 'methane.extxyz'
    #output = 'out'
    #select = ':'    
    #nice = 'nice.pickle'
    #nblocks = 1
    
    #ASE read inputs
    train_subset = args.train_subset
    #train_subset_num = [int(s) for s in re.findall(r'\b\d+\b', train_subset)][1]
    #test_subset = args.test_subset
    environments_for_fitting = args.environments_for_fitting
    
    #Hyper inputs
    ic = args.interaction_cutoff
    n = args.max_radial
    l = args.max_angular
    sig = args.gaussian_sigma_constant
    json_hypers = json.loads(args.json)
    
    #get_NICE inputs
    numexcov = args.numexpcov
    numexpinv = args.numexpinv
    maxtakecov = args.maxtakecov
    maxtakeinv = args.maxtakeinv
    ncompcov = args.ncompcov
    ncompinv = args.ncompinv
    
    
    #Output file
    if output == "":
        output = os.path.splitext(filename)[0]
        
        
    #Some constants    
    HARTREE_TO_EV = 27.211386245988
    
    #grid = [] #for learning curve, should there be a pattern in forming this grid
    #gr1=1;
    #grid_point=0;
    #While grid_point<train_subset_num: 
    #    grid_point=102.44*math.exp(gr1*0.3837);
    #    grid.append(grid_point)
    #    gr1+=1
        
    #print("Using the grid:",grid)
    
    #Building HYPERS
    HYPERS = { **{
    'interaction_cutoff': ic,
    'max_radial': n,
    'max_angular': l,
    'gaussian_sigma_type': 'Constant',
    'gaussian_sigma_constant': sig,
    'cutoff_smooth_width': 0.3,
    'radial_basis': 'GTO'
    }, **json_hypers }
  
    """
    Definitions of what we seem to be doing!
    StandardSequence --> Block implementing logic of main NICE sequence.
    StandardBlock --> Block for standard procedure of body order increasement step for covariants and invariants.
    a. ThresholdExpansioner --> Covariant [Block to do Clebsch-Gordan iteration. It uses two even-odd pairs of Data instances with covariants
    to produce new ones. If first even-odd pair contains covariants of body order v1, and the second v2, body
    order of the result would be v1 + v2.]
    b. CovariantsPurifierBoth --> Covariant [Block to purify covariants of both parities. It operates with pairs of instances of Data class with covariants]
    c. IndividualLambdaPCAsBoth --> Covariant [Block to do pca step for covariants of both parities. It operates with even-odd pairs of instances of Data class]
    d. ThresholdExpansioner --> Invariant [Block to do Clebsch-Gordan iteration.]
    e. InvariantsPurifier --> Invariant [Block to purify invariants. It operates with numpy 2d arrays containing invariants]
    f. InvariantsPCA --> Invariant [Block to do pca step for invariants. It operates with 2d numpy arrays]

    """
    sb = [ ]
    def get_nice():
        numax = 4;
        for nu in range(1, numax-1): # this starts from nu=2 actually
            sb.append(
                StandardBlock(ThresholdExpansioner(num_expand=numexpcov),
                      CovariantsPurifierBoth(max_take=maxtakecov),
                      IndividualLambdaPCAsBoth(n_components=ncompcov),
                      ThresholdExpansioner(num_expand=numexpinv, mode='invariants'),
                      InvariantsPurifier(max_take=maxtakeinv),
                      InvariantsPCA(n_components=ncompinv)) 
                         )
                         
    # at the last order, we only need invariants
        sb.append(
                StandardBlock(None, None, None,
                         ThresholdExpansioner(num_expand=numexpinv, mode='invariants'),
                         InvariantsPurifier(max_take=maxtakeinv),
                         InvariantsPCA(n_components=ncompinv)) 
                         )
    
    return StandardSequence(sb,initial_scaler=InitialScaler(mode='signal integral', individually=True))
    
    
    
    #Reading the file into training and testing  
    print("Loading structures for train ", filename, " frames: ", train_subset)    
    train_structures = ase.io.read(filename, index=train_subset)
    #print("Loading structures for test ", filename, " frames: ", test_subset)
    #test_structures = ase.io.read(filename, index=test_subset)
    
    all_species = get_all_species(train_structures)
    
    #calculating the coefficiencts
    """
    [environmental index, radial basis/neighbor specie index, lambda, m] with spherical expansion coefficients for 
        environments around atoms with specie indicated in key.
    """
    train_coefficients = get_spherical_expansion(train_structures, HYPERS, all_species)
    #test_coefficients = get_spherical_expansion(test_structures, HYPERS, all_species)
    
    if args.which_output:
        #individual nice transformers for each atomic specie in the dataset
        nice = {}
        for key in train_coefficients.keys():
            nice[key] = get_nice()
    else:
        #Now that we have the coefficients, we want to fit a single nice transformer irrespective of the specie
        #1. Take all coefficients for each specie and merge all the coefficients together.Then based on the user-defined number of environments to be used for fitting, we choose the required number of coefficients.
        all_coefficients = [train_coefficients[key] for key in train_coefficients.keys()]
        all_coefficients = np.concatenate(all_coefficients, axis=0)
        np.random.shuffle(all_coefficients)
        all_coefficients = all_coefficients[0:environments_for_fitting]
        #2. Use the model to fit nice on the coefficients chosen above
        nice_single = get_nice()
        nice_single.fit(all_coefficients)
        #3. Irrespective of the central specie, we use the same nice transformer
        nice = {specie: nice_single for specie in all_species}
    
    HYPERS["ncompcov"] = ncompcov
    HYPERS["ncompinv"] = ncompinv
    HYPERS["numexpcov"] = numexpcov
    HYPERS["numexpinv"] = numexpinv               
    HYPERS["reference-file"] = filename
    HYPERS["reference-sel"] = train_subset
    
    print("Dumping NICE model")    
    pickle.dump( { 
               "HYPERS" : HYPERS, 
               "NICE": nice,
             }, open(output+".pickle", "wb"))
    
if __name__ == '__main__':
    main()      