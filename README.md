# flipMC
Project on MD/MC sampling for binding mode flips

The script  in input/MCMD.py randomly alternates between MD moves (that move all particles in the system) and MC moves (that only change certain dihedral angles in a single molecule). To run it

    ~/sire.app/bin/python MCMD.py


The relative probabilities of carrying out an MD or MC move is determine by the variables 
  
    MDMOVE_WEIGHT = 10
    MCMOVE_WEIGHT = 1
    
  In the above this would give a 10/11 change of doing an MD move, versus a 1/11 chance of doing an MC move. 
  
  How the ligand is moved is defined by the contents of the flex file
  
    version 1
    molecule LIG
    rigidbody rotate 0.000 translate 0.000
    maximumbondvariables 0  
    maximumanglevariables 0  
    maximumdihedralvariables 1  
    dihedral C2   C3   C9   C10   flex 180.00
    
    
The above example would only change 1 dihedral by a random number taken in the interval +/- 180 degrees. 

So if the dihedral angle value is 30 degrees, the MC move will select a new value between -150/210 degrees.


The output file moves.dat contain useful information

    WeightedMoves{
     1 : weight == 10, timing = 2.76299 ms
       MolecularDynamics( OpenMMMDIntegrator(), timeStep() == 2 fs, nMoves() == 9093 )
    2 : weight == 1, timing = 6.77949 ms
       InternalMove( nAccepted() = 214 nRejected() == 693 )
    }
    
 The acceptance rate of the MC move is equal to nAccepted/(nAccepted+nRejected)
 The timing is the average time for doing one move. 
 
 In the current setup MD moves are fast because the example is taken from a vacuum simulation. We will monitor what the timings look like when simulating solvated systems.
 
 Some Parameters that may need tweaks. 
 
    Parameter("nmoves", ...
    Parameter("ncycles", ...
    Parameter("buffered coordinates frequency", 0,   
    Parameter("cutoff type", "nocutoff"
    
At each cycle, a MC or MD move type is selected, and then followed by nmoves integration steps (MD) or internal move trials (MC). 
Must set cutoff type to cutoffperiodic if loading an input file with PBC set. The script currently only saves one snapshot after each cycle because buffered coordinates frequency is set to 0. This parameter doesn't work with MC moves. For testing purposes one can run a large number of cycles with fewer moves per cycles. This could have a negative impact on performance due to overheads of creating Sire/OpenMM systems. This could be optimised later, so we will not worry about it initially unless the performance is really poor. The script doesn't currently work for free energy calculations. 

