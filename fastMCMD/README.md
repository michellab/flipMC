# flipMC
Project on MD/MC sampling for binding mode flips

New implementation. The script MCMD2.py sequentially alternates between MD moves and MC moves (that only change certain dihedral angles in a single molecule). To run it

    ~/sire.app/bin/python MCMD2.py

The number of MD or MC moves done in one cycle is controlled by 

nmoves = Parameter("nmoves", 100, """Number of Molecular Dynamics moves to be performed per cycle.""")

nmcmoves = Parameter("nmcmoves",0, """Number of Monte Carlo Internal moves to be performed per cycle.""")

To disable MD and run MC only set nmoves to 0. 
TO disable MC and run md only set nmcmoves to 0.

The output file moves.dat will show statistics for both moves used during the simulation.

[WeightedMoves{
  1 : weight == 1, timing = 0.117761 ms
       MolecularDynamics( OpenMMMDIntegrator(), timeStep() == 2 fs, nMoves() == 10000 )
}, WeightedMoves{
  1 : weight == 1, timing = 0 ms
       InternalMove( nAccepted() = 0 nRejected() == 0 )
}]
