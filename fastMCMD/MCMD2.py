
####################################################################################################
#                                                                                                  #
#   RUN SCRIPT to perform an MD simulation in Sire with OpenMM                                     #
#                                                                                                  #
#   author: Julien Michel                                                                          #
#   author: Gaetano Calabro                                                                        #
#   author: Antonia Mey <antonia.mey@ed.ac.uk>                                                     #
#                                                                                                  #
####################################################################################################

####################################################################################################
#
#   IMPORTS
#
####################################################################################################

import os
import re
import sys

from Sire.Base import *

# Make sure that the OPENMM_PLUGIN_DIR enviroment variable is set correctly if unset.
try:
    # The user has already set the plugin location.
    os.environ["OPENMM_PLUGIN_DIR"]
except KeyError:
    # Set to the default location of the bundled OpenMM package.
    os.environ["OPENMM_PLUGIN_DIR"] = getLibDir() + "/plugins"

from Sire.IO import *
from Sire.Mol import *
from Sire.CAS import *
from Sire.System import *
from Sire.Move import *
from Sire.MM import *
from Sire.FF import *
from Sire.Units import *
from Sire.Vol import *
from Sire.Maths import *
from Sire.Qt import *
from Sire.ID import *
from Sire.Config import *
from Sire.Analysis import *
from Sire.Tools.DCDFile import *
from Sire.Tools import Parameter, resolveParameters
import Sire.Stream
import time
import numpy as np

####################################################################################################
#
#   Config file parameters
#
####################################################################################################
gpu = Parameter("gpu", 0, """The device ID of the GPU on which to run the simulation.""")

rf_dielectric = Parameter("reaction field dielectric", 78.3,
                          """Dielectric constant to use if the reaction field cutoff method is used.""")

temperature = Parameter("temperature", 25 * celsius, """Simulation temperature""")

MCtemperature = Parameter("MCtemperature", 25 * celsius, """Simulation temperature""")

pressure = Parameter("pressure", 1 * atm, """Simulation pressure""")

topfile = Parameter("topfile", "lig2.prm7",
                    """File name of the topology file containing the system to be simulated.""")

crdfile = Parameter("crdfile", "lig2.rst7",
                    """File name of the coordinate file containing the coordinates of the
                       system to be simulated.""")

s3file = Parameter("s3file", "SYSTEM.s3",
                   """Filename for the system state file. The system state after topology and and coordinates
                   were loaded are saved in this file.""")

restart_file = Parameter("restart file", "sim_restart.s3",
                         """Filename of the restart file to use to save progress during the simulation.""")

dcd_root = Parameter("dcd root", "traj", """Root of the filename of the output DCD trajectory files.""")

nmoves = Parameter("nmoves", 1000, """Number of Molecular Dynamics moves to be performed per cycle.""")

nmcmoves = Parameter("nmcmoves", 10, """Number of Monte Carlo Internal moves to be performed per cycle.""")

random_seed = Parameter("random seed", None, """Random number seed. Set this if you
                         want to have reproducible simulations.""")

ncycles = Parameter("ncycles", 100,
                    """The number of MD/MC cycles. The total elapsed time will be nmoves*ncycles*timestep""")

maxcycles = Parameter("maxcycles",99999,
                      """The maximum number of MD cycles to carry out. Useful to restart simulations from a checkpoint""")

ncycles_per_snap = Parameter("ncycles_per_snap", 1, """Number of cycles between saving snapshots""")

save_coords = Parameter("save coordinates", True, """Whether or not to save coordinates.""")

buffered_coords_freq = Parameter("buffered coordinates frequency", 0,
                                 """The number of time steps between saving of coordinates during
                                 a cycle of MD. 0 disables buffering.""")
minimal_coordinate_saving = Parameter("minimal coordinate saving", False, "Reduce the number of coordiantes writing for states"
                                                                    "with lambda in ]0,1[")

time_to_skip = Parameter("time to skip", 0 * picosecond, """Time to skip in picoseconds""")

minimise = Parameter("minimise", True, """Whether or not to perform minimization before the simulation.""")

minimise_tol = Parameter("minimise tolerance", 1, """Tolerance used to know when minimization is complete.""")

minimise_max_iter = Parameter("minimise maximum iterations", 1000, """Maximum number of iterations for minimization.""")

equilibrate = Parameter("equilibrate", False , """Whether or not to perform equilibration before dynamics.""")

equil_iterations = Parameter("equilibration iterations", 2000, """Number of equilibration steps to perform.""")

equil_timestep = Parameter("equilibration timestep", 0.5 * femtosecond, """Timestep to use during equilibration.""")

combining_rules = Parameter("combining rules", "arithmetic",
                            """Combining rules to use for the non-bonded interactions.""")

timestep = Parameter("timestep", 2 * femtosecond, """Timestep for the dynamics simulation.""")

platform = Parameter("platform", "CPU", """Which OpenMM platform should be used to perform the dynamics.""")

precision = Parameter("precision", "mixed", """The floating point precision model to use during dynamics.""")

constraint = Parameter("constraint", "hbonds", """The constraint model to use during dynamics.""")

cutoff_type = Parameter("cutoff type", "nocutoff", """The cutoff method to use during the simulation.""")

cutoff_dist = Parameter("cutoff distance", 10 * angstrom,
                        """The cutoff distance to use for the non-bonded interactions.""")

integrator_type = Parameter("integrator", "leapfrogverlet", """The integrator to use for dynamics.""")

inverse_friction = Parameter("inverse friction", 0.1 * picosecond,
                             """Inverse friction time for the Langevin thermostat.""")

andersen = Parameter("thermostat", True,
                     """Whether or not to use the Andersen thermostat (needed for NVT or NPT simulation).""")

barostat = Parameter("barostat", False, """Whether or not to use a barostat (needed for NPT simulation).""")

andersen_frequency = Parameter("andersen frequency", 10.0, """Collision frequency in units of (1/ps)""")

barostat_frequency = Parameter("barostat frequency", 25,
                               """Number of steps before attempting box changes if using the barostat.""")

lj_dispersion = Parameter("lj dispersion", False, """Whether or not to calculate and include the LJ dispersion term.""")

cmm_removal = Parameter("center of mass frequency", 10,
                        "Frequency of which the system center of mass motion is removed.""")

center_solute = Parameter("center solute", False,
                          """Whether or not to centre the centre of geometry of the solute in the box.""")

use_restraints = Parameter("use restraints", False, """Whether or not to use harmonic restaints on the solute atoms.""")

k_restraint = Parameter("restraint force constant", 100.0, """Force constant to use for the harmonic restaints.""")

heavy_mass_restraint = Parameter("heavy mass restraint", 1.10,
                                 """Only restrain solute atoms whose mass is greater than this value.""")

unrestrained_residues = Parameter("unrestrained residues", ["WAT", "HOH"],
                                  """Names of residues that are never restrained.""")

freeze_residues = Parameter("freeze residues", False, """Whether or not to freeze certain residues.""")

frozen_residues = Parameter("frozen residues", ["LGR", "SIT", "NEG", "POS"],
                            """List of residues to freeze if 'freeze residues' is True.""")


use_distance_restraints = Parameter("use distance restraints", False,
                                    """Whether or not to use restraints distances between pairs of atoms.""")

distance_restraints_dict = Parameter("distance restraints dictionary", {},
                                     """Dictionary of pair of atoms whose distance is restrained, and restraint
                                     parameters. Syntax is {(atom0,atom1):(reql, kl, Dl)} where atom0, atom1 are atomic
                                     indices. reql the equilibrium distance. Kl the force constant of the restraint.
                                     D the flat bottom radius. WARNING: PBC distance checks not implemented, avoid
                                     restraining pair of atoms that may diffuse out of the box.""")

hydrogen_mass_repartitioning_factor = Parameter("hydrogen mass repartitioning factor",None,
                                     """If not None and is a number, all hydrogen atoms in the molecule will
                                        have their mass increased by the input factor. The atomic mass of the heavy atom
                                        bonded to the hydrogen is decreased to keep the mass constant.""")

## Free energy specific keywords
morphfile = Parameter("morphfile", "MORPH.pert",
                      """Name of the morph file containing the perturbation to apply to the system.""")

lambda_val = Parameter("lambda_val", 0.0,
                       """Value of the lambda parameter at which to evaluate free energy gradients.""")

delta_lambda = Parameter("delta_lambda", 0.001,
                         """Value of the lambda interval used to evaluate free energy gradients by finite difference.""")

lambda_array = Parameter("lambda array",[] ,
                        """Array with all lambda values lambda_val needs to be part of the array. """)

shift_delta = Parameter("shift delta", 2.0,
                        """Value of the Lennard-Jones soft-core parameter.""")

coulomb_power = Parameter("coulomb power", 0,
                          """Value of the Coulombic soft-core parameter.""")

energy_frequency = Parameter("energy frequency", 1,
                             """The number of time steps between evaluation of free energy gradients.""")

simfile = Parameter("outdata_file", "simfile.dat", """Filename that records all output needed for the free energy analysis""")

perturbed_resnum = Parameter("perturbed residue number",1,"""The residue number of the molecule to morph.""")

verbose = Parameter("verbose", False, """Print debug output""")

####################################################################################################
#
#   Helper functions
#
####################################################################################################

def setupDCD(system):
    r"""
    Parameters:
    ----------
    system : sire system
        sire system to be saved
    Return:
    ------
    trajectory : trajectory
    """
    files = os.listdir(os.getcwd())
    dcds = []
    for f in files:
        if f.endswith(".dcd"):
            dcds.append(f)

    dcds.sort()

    index = len(dcds) + 1

    dcd_filename = dcd_root.val + "%0009d" % index + ".dcd"
    softcore_almbda = True
    if lambda_val.val == 1.0 or lambda_val.val == 0.0:
        softcore_almbda = False
    if minimal_coordinate_saving.val and softcore_almbda:
        interval = ncycles.val*nmoves.val
        Trajectory = DCDFile(dcd_filename, system[MGName("all")], system.property("space"), timestep.val, interval)
    else:
        Trajectory = DCDFile(dcd_filename, system[MGName("all")], system.property("space"), timestep.val,
                         interval=buffered_coords_freq.val * ncycles_per_snap.val)

    return Trajectory


def writeSystemData(system, moves, Trajectory, block, softcore_lambda=False):

    if softcore_lambda:
        if block == ncycles.val or block == 1:
            Trajectory.writeModel(system[MGName("all")], system.property("space"))
    else:
        if block % ncycles_per_snap.val == 0:
            if buffered_coords_freq.val > 0:
                dimensions = {}
                sysprops = system.propertyKeys()
                for prop in sysprops:
                    if prop.startswith("buffered_space"):
                        dimensions[str(prop)] = system.property(prop)
                Trajectory.writeBufferedModels(system[MGName("all")], dimensions)
            else:
                Trajectory.writeModel(system[MGName("all")], system.property("space"))

    # Write an AMBER RST coordinate file each cycle.
    #rst = AmberRst(system)
    #rst.writeToFile("latest.rst")
    
    moves_file = open("moves.dat", "w")
    print("%s" % moves, file=moves_file)
    moves_file.close()


def centerSolute(system, space):

    # ! Assuming first molecule in the system is the solute !

    if space.isPeriodic():
        box_center = space.dimensions() / 2
    else:
        box_center = Vector(0.0, 0.0, 0.0)

    solute = system.molecules().at(MolNum(1))[0].molecule() 

    solute_cog = CenterOfGeometry(solute).point()

    delta = box_center - solute_cog

    molNums = system.molNums()

    for molnum in molNums:
        mol = system.molecule(molnum)[0].molecule()
        molcoords = mol.property("coordinates")
        molcoords.translate(delta)
        mol = mol.edit().setProperty("coordinates", molcoords).commit()
        system.update(mol)

    return system


def createSystem(molecules):
    #print("Applying flexibility and zmatrix templates...")
    print("Creating the system...")

    moleculeNumbers = molecules.molNums()
    moleculeList = []

    for moleculeNumber in moleculeNumbers:
        molecule = molecules.molecule(moleculeNumber)[0].molecule()
        moleculeList.append(molecule)

    molecules = MoleculeGroup("molecules")
    ions = MoleculeGroup("ions")

    for molecule in moleculeList:
        natoms = molecule.nAtoms()
        if natoms == 1:
            ions.add(molecule)
        else:
            molecules.add(molecule)

    all = MoleculeGroup("all")
    all.add(molecules)
    all.add(ions)

    # Add these groups to the System
    system = System()

    system.add(all)
    system.add(molecules)
    system.add(ions)

    return system


def setupForcefields(system, space):

    print("Creating force fields... ")

    all = system[MGName("all")]
    molecules = system[MGName("molecules")]
    ions = system[MGName("ions")]

    # - first solvent-solvent coulomb/LJ (CLJ) energy
    internonbondedff = InterCLJFF("molecules:molecules")
    if (cutoff_type.val != "nocutoff"):
        internonbondedff.setUseReactionField(True)
        internonbondedff.setReactionFieldDielectric(rf_dielectric.val)
    internonbondedff.add(molecules)

    inter_ions_nonbondedff = InterCLJFF("ions:ions")
    if (cutoff_type.val != "nocutoff"):
        inter_ions_nonbondedff.setUseReactionField(True)
        inter_ions_nonbondedff.setReactionFieldDielectric(rf_dielectric.val)

    inter_ions_nonbondedff.add(ions)

    inter_ions_molecules_nonbondedff = InterGroupCLJFF("ions:molecules")
    if (cutoff_type.val != "nocutoff"):
        inter_ions_molecules_nonbondedff.setUseReactionField(True)
        inter_ions_molecules_nonbondedff.setReactionFieldDielectric(rf_dielectric.val)

    inter_ions_molecules_nonbondedff.add(ions, MGIdx(0))
    inter_ions_molecules_nonbondedff.add(molecules, MGIdx(1))

    # Now solute bond, angle, dihedral energy
    intrabondedff = InternalFF("molecules-intrabonded")
    intrabondedff.add(molecules)

    # Now solute intramolecular CLJ energy
    intranonbondedff = IntraCLJFF("molecules-intranonbonded")

    if (cutoff_type.val != "nocutoff"):
        intranonbondedff.setUseReactionField(True)
        intranonbondedff.setReactionFieldDielectric(rf_dielectric.val)

    intranonbondedff.add(molecules)

    # solute restraint energy
    #
    # We restrain atoms based ont he contents of the property "restrainedatoms"
    #
    restraintff = RestraintFF("restraint")

    if use_restraints.val:
        molnums = molecules.molecules().molNums()

        for molnum in molnums:
            mol = molecules.molecule(molnum)[0].molecule()
            try:
                mol_restrained_atoms = propertyToAtomNumVectorList(mol.property("restrainedatoms"))
            except UserWarning as error:
                error_type = re.search(r"(Sire\w*::\w*)", str(error)).group(0)
                if error_type == "SireBase::missing_property":
                    continue
                else:
                    raise error

            for restrained_line in mol_restrained_atoms:
                atnum = restrained_line[0]
                restraint_atom = mol.select(atnum)
                restraint_coords = restrained_line[1]
                restraint_k = restrained_line[2] * kcal_per_mol / (angstrom * angstrom)

                restraint = DistanceRestraint.harmonic(restraint_atom, restraint_coords, restraint_k)

                restraintff.add(restraint)

    # Here is the list of all forcefields
    forcefields = [internonbondedff, intrabondedff, intranonbondedff, inter_ions_nonbondedff,
                   inter_ions_molecules_nonbondedff, restraintff]

    for forcefield in forcefields:
        system.add(forcefield)

    system.setProperty("space", space)
    system.setProperty("switchingFunction", CHARMMSwitchingFunction(cutoff_dist.val))
    system.setProperty("combiningRules", VariantProperty(combining_rules.val))

    total_nrg = internonbondedff.components().total() + \
                intranonbondedff.components().total() + intrabondedff.components().total() + \
                inter_ions_nonbondedff.components().total() + inter_ions_molecules_nonbondedff.components().total() + \
                restraintff.components().total()

    e_total = system.totalComponent()

    system.setComponent(e_total, total_nrg)

    # Add a monitor that calculates the average total energy and average energy
    # deltas - we will collect both a mean average and an zwanzig average
    system.add("total_energy", MonitorComponent(e_total, Average()))

    return system

def setupMCmoves(system, random_seed):
    # Now create an Internal MC move that works on the solute only
    ligand = system[MolNum(LIGAND_NUM)][0]
    ligand = ligand.edit().rename(LIGAND_NAME).commit()
    # This will add the property "flexibility" to the solute
    flexibility_lib = FlexibilityLibrary(LIGAND_FLEX_FILE)
    flexibility = flexibility_lib.getFlexibility(ligand)
    ligand = ligand.edit().setProperty("flexibility", flexibility).commit()
    
    ligand_grp = MoleculeGroup("ligand",ligand)
    ligand_intra_moves = InternalMove( ligand_grp )

    # make sure that the ligand is updated in the System
    system.update(ligand)
    # also make sure that the MoleculeGroup used by the sampler
    # is also in the System
    system.add(ligand_grp)
    
    moves = WeightedMoves()
    moves.add(ligand_intra_moves,1)
    moves.setTemperature(MCtemperature.val)

    print("Create an internal MC move for the ligand")
    
    if (not random_seed):
        random_seed = RanGenerator().randInt(100000, 1000000)
    print("Generated random seed number %d " % random_seed)

    moves.setGenerator(RanGenerator(random_seed))

    return moves

    
def setupMoves(system, random_seed, GPUS):

    print("Setting up moves...")

    molecules = system[MGName("all")]

    Integrator_OpenMM = OpenMMMDIntegrator(molecules)

    Integrator_OpenMM.setPlatform(platform.val)
    Integrator_OpenMM.setConstraintType(constraint.val)
    Integrator_OpenMM.setCutoffType(cutoff_type.val)
    Integrator_OpenMM.setIntegrator(integrator_type.val)
    Integrator_OpenMM.setFriction(inverse_friction.val)  # Only meaningful for Langevin/Brownian integrators
    Integrator_OpenMM.setPrecision(precision.val)
    Integrator_OpenMM.setTimetoSkip(time_to_skip.val)

    Integrator_OpenMM.setDeviceIndex(str(GPUS))
    Integrator_OpenMM.setLJDispersion(lj_dispersion.val)

    if cutoff_type.val != "nocutoff":
        Integrator_OpenMM.setCutoffDistance(cutoff_dist.val)
    if cutoff_type.val == "cutoffperiodic":
        Integrator_OpenMM.setFieldDielectric(rf_dielectric.val)

    Integrator_OpenMM.setCMMremovalFrequency(cmm_removal.val)

    Integrator_OpenMM.setBufferFrequency(buffered_coords_freq.val)

    if use_restraints.val:
        Integrator_OpenMM.setRestraint(True)

    if andersen.val:
        Integrator_OpenMM.setTemperature(temperature.val)
        Integrator_OpenMM.setAndersen(andersen.val)
        Integrator_OpenMM.setAndersenFrequency(andersen_frequency.val)

    if barostat.val:
        Integrator_OpenMM.setPressure(pressure.val)
        Integrator_OpenMM.setMCBarostat(barostat.val)
        Integrator_OpenMM.setMCBarostatFrequency(barostat_frequency.val)

    #print Integrator_OpenMM.getDeviceIndex()
    Integrator_OpenMM.initialise()

    mdmove = MolecularDynamics(molecules, Integrator_OpenMM, timestep.val,
                               {"velocity generator": MaxwellBoltzmann(temperature.val)})

    print("Created a MD move that uses OpenMM for all molecules on %s " % GPUS)

    moves = WeightedMoves()
    moves.add(mdmove, 1)
    
    if (not random_seed):
        random_seed = RanGenerator().randInt(100000, 1000000)
    print("Generated random seed number %d " % random_seed)

    moves.setGenerator(RanGenerator(random_seed))

    return moves


def atomNumListToProperty(list):

    prop = Properties()
    i = 0
    for value in list:
        prop.setProperty(str(i), VariantProperty(value.value()))
        i += 1
    return prop


def atomNumVectorListToProperty(list):
    prop = Properties()

    i = 0

    for value in list:
        prop.setProperty("AtomNum(%d)" % i, VariantProperty(value[0].value()))
        prop.setProperty("x(%d)" % i, VariantProperty(value[1].x()))
        prop.setProperty("y(%d)" % i, VariantProperty(value[1].y()))
        prop.setProperty("z(%d)" % i, VariantProperty(value[1].z()))
        prop.setProperty("k(%d)" % i, VariantProperty(value[2].val ) )
        i += 1

    prop.setProperty("nrestrainedatoms", VariantProperty(i));

    return prop


def linkbondVectorListToProperty(list):

    prop = Properties()

    i = 0

    for value in list:
        prop.setProperty("AtomNum0(%d)" % i, VariantProperty(value[0]))
        prop.setProperty("AtomNum1(%d)" % i, VariantProperty(value[1]))
        prop.setProperty("reql(%d)" % i, VariantProperty(value[2]))
        prop.setProperty("kl(%d)" % i, VariantProperty(value[3]))
        prop.setProperty("dl(%d)" % i, VariantProperty(value[4]))
        i += 1

    prop.setProperty("nbondlinks", VariantProperty(i));

    return prop


def propertyToAtomNumList(prop):
    list = []
    i = 0
    try:
        while True:
            list.append(AtomNum(prop[str(i)].toInt()))
            i += 1
    except:
        pass
    return list

def propertyToAtomNumVectorList(prop):
    list = []
    i = 0
    try:
        while True:
            num = AtomNum(prop["AtomNum(%d)" % i].toInt())
            x = prop["x(%d)" % i].toDouble()
            y = prop["y(%d)" % i].toDouble()
            z = prop["z(%d)" % i].toDouble()
            k = prop["k(%d)" % i].toDouble()

            list.append((num, Vector(x, y, z), k ))

            i += 1
    except:
        pass

    return list


def setupRestraints(system):

    molecules = system[MGName("all")].molecules()

    molnums = molecules.molNums()

    for molnum in molnums:
        mol = molecules.molecule(molnum)[0].molecule()
        nats = mol.nAtoms()
        atoms = mol.atoms()

        restrainedAtoms = []

        #
        # This will apply a restraint to every atom that is
        # A) NOT a hydrogen
        # B) NOT in an unrestrained residue.
        #
        for x in range(0, nats):
            at = atoms[x]
            atnumber = at.number()
            #print at, atnumber
            if at.residue().name().value() in unrestrained_residues.val:
                continue
            #print at, at.property("mass"), heavyMass
            if ( at.property("mass").value() < heavy_mass_restraint.val ):
                #print "LIGHT, skip"
                continue
            atcoords = at.property("coordinates")
            #print at
            restrainedAtoms.append((atnumber, atcoords, k_restraint))

            #restrainedAtoms.append( atnumber )

        if len(restrainedAtoms) > 0:
            mol = mol.edit().setProperty("restrainedatoms", atomNumVectorListToProperty(restrainedAtoms)).commit()
            #print restrainedAtoms
            #print propertyToAtomNumVectorList( mol.property("restrainedatoms") )
            system.update(mol)

    return system


def setupDistanceRestraints(system, restraints=None):
    prop_list = []

    molecules = system[MGName("all")].molecules()
    
    if restraints is None:
        #dic_items = list(distance_restraints_dict.val.items())
        dic_items = list(dict(distance_restraints_dict.val).items())
    else:
        dic_items = list(restraints.items())

    for i in range(0, molecules.nMolecules()):
        mol = molecules.molecule(MolNum(i + 1))[0].molecule()
        atoms_mol = mol.atoms()
        natoms_mol = mol.nAtoms()
        for j in range(0, natoms_mol):
            at = atoms_mol[j]
            atnumber = at.number()
            for k in range(len(dic_items)):
                if dic_items[k][0][0] == dic_items[k][0][1]:
                    print ("Error! It is not possible to place a distance restraint on the same atom")
                    sys.exit(-1)
                if atnumber.value() - 1 in dic_items[k][0]:
                    print (at)
                    # atom0index atom1index, reql, kl, dl
                    prop_list.append((
                        dic_items[k][0][0] + 1, dic_items[k][0][1] + 1, dic_items[k][1][0], dic_items[k][1][1],
                        dic_items[k][1][2]))

    unique_prop_list = []

    [unique_prop_list.append(item) for item in prop_list if item not in unique_prop_list]
    print (unique_prop_list)
    #Mol number 0 will store all the information related to the bond-links in the system
    mol0 = molecules.molecule(MolNum(1))[0].molecule()
    mol0 = mol0.edit().setProperty("linkbonds", linkbondVectorListToProperty(unique_prop_list)).commit()
    system.update(mol0)

    return system


def freezeResidues(system):

    molecules = system[MGName("all")].molecules()
    molnums = molecules.molNums()

    for molnum in molnums:
        mol = molecules.molecule(molnum)[0].molecule()
        nats = mol.nAtoms()
        atoms = mol.atoms()

        for x in range(0, nats):
            at = atoms[x]
            atnumber = at.number()
            if at.residue().name().value() in frozen_residues.val:
                print("Freezing %s %s %s " % (at, atnumber, at.residue().name().value() ))
                mol = at.edit().setProperty("mass", 0 * g_per_mol).molecule()

        system.update(mol)

    return system

def repartitionMasses(system, hmassfactor=4.0):
    """
    Increase the mass of hydrogen atoms to hmass times * amu, and subtract the mass 
increase from the heavy atom the hydrogen is bonded to.
    """

    print ("Applying Hydrogen Mass repartition to input using a factor of %s " % hmassfactor)

    molecules = system[MGName("all")].molecules()

    molnums = molecules.molNums()

    for molnum in molnums:
        mol = molecules.molecule(molnum)[0].molecule()
        nats = mol.nAtoms()
        atoms = mol.atoms()

        if nats == 1:
            connect = None
        else:
            connect = mol.property("connectivity")

        atom_masses = {}

        #
        # First pass. Initialise changes in atom_masses to effect
        #
        for x in range(0,nats):
            at = atoms[x]
            atidx = at.index()
            atom_masses[atidx.value()] = 0 * g_per_mol

        total_delta = 0.0 * g_per_mol

        #
        # Second pass. Decide how the mass of each atom should change.
        #
        for x in range(0,nats):
            at = atoms[x]
            atidx = at.index()
            atmass = at.property("mass")

            # units are in g_per_mol
            if (atmass.value() < 1.1):
                # Atoms with a mass < 1.1 g_per_mol are assumed to be hydrogen atoms
                atmass = at.property("mass")
                deltamass = atmass * hmassfactor - atmass
                #print("Increasing mass %s by %s  " % (at, deltamass))
                total_delta += deltamass
                atom_masses[atidx.value()] = deltamass
                # Skip monoatomic systems without connectivity property
                if connect is None:
                    continue
                bonds = connect.getBonds(atidx)
                # Get list of atoms that share one bond with this atom. Ignore all atoms that have a
                # mass < 1.1 g_mol in the ORIGINAL atoms list
                # For each atom this was bonded to, substract delta_mass / nbonded
                bonded_atoms = []
                for bond in bonds:
                    at0 = mol.select(bond.atom0()).index()
                    at1 = mol.select(bond.atom1()).index()
                    if at0 == atidx:
                        heavyatidx = at1
                    else:
                        heavyatidx = at0

                    if heavyatidx in bonded_atoms:
                        continue
                    heavyat = mol.select(heavyatidx)
                    heavyat_mass = heavyat.property("mass")
                    # units are in g_per_mol
                    if heavyat_mass.value() < 1.1:
                        continue
                    bonded_atoms.append(heavyatidx)

                for bonded_atom in bonded_atoms:
                    #print("Increasing mass %s by %s  " % (mol.select(bonded_atom), -deltamass))
                    total_delta += - deltamass
                    atom_masses[bonded_atom.value()] += - deltamass

        # Sanity check (g_per_mol)
        if total_delta.value() > 0.001:
            print ("WARNING ! The mass repartitioning algorithm is not conserving atomic masses for",
                   "molecule %s (total delta is %s). Report bug to a Sire developer." % (molnum,total_delta.value()) )
            sys.exit(-1)

        # Now that have worked out mass changes per molecule, update molecule
        for x in range(0,nats):
            at = atoms[x]
            atidx = at.index()
            atmass = at.property("mass")
            newmass = atmass + atom_masses[atidx.value()]
            # Sanity check. Note this is likely to occur if hmassfactor > 4
            if (newmass.value() < 0.0):
                print ("""WARNING ! The mass of atom %s is less than zero after hydrogen mass repartitioning.
                        This should not happen ! Decrease hydrogen mass repartitioning factor in your cfg file
                        and try again.""" % atidx)
                sys.exit(-1)

            mol = mol.edit().atom(atidx).setProperty("mass", newmass )[0].molecule()

        system.update(mol)
        
    return system

def getDummies(molecule):
    print ("Selecting dummy groups")
    natoms = molecule.nAtoms()
    atoms = molecule.atoms()

    from_dummies = None
    to_dummies = None

    for x in range(0, natoms):
        atom = atoms[x]
        if atom.property("initial_ambertype") == "du":
            if from_dummies is None:
                from_dummies = molecule.selectAll(atom.index())
            else:
                from_dummies += molecule.selectAll(atom.index())
        elif atom.property("final_ambertype") == "du":
            if to_dummies is None:
                to_dummies = molecule.selectAll(atom.index())
            else:
                to_dummies += molecule.selectAll(atom.index())

    return to_dummies, from_dummies


def createSystemFreeEnergy(molecules):
    r"""creates the system for free energy calculation
    Parameters
    ----------
    molecules : Sire.molecules
        Sire object that contains a lot of information about molecules
    Returns
    -------
    system : Sire.system

    """
    print ("Create the System...")

    moleculeNumbers = molecules.molNums()
    moleculeList = []

    for moleculeNumber in moleculeNumbers:
        molecule = molecules.molecule(moleculeNumber)[0].molecule()
        moleculeList.append(molecule)

    # Scan input to find a molecule with passed residue number 
    # The residue name of the first residue in this molecule is
    # used to name the solute. This is used later to match
    # templates in the flex/pert files.

    solute = None
    for molecule in moleculeList:
        if ( molecule.residue(ResIdx(0)).number() == ResNum(perturbed_resnum.val) ):
            solute = molecule
            moleculeList.remove(molecule)
            break

    if solute is None:
        print ("FATAL ! Could not find a solute to perturb with residue number %s in the input ! Check the value of your cfg keyword 'perturbed residue number'" % perturbed_resnum.val)
        sys.exit(-1)

    #solute = moleculeList[0]

    lig_name = solute.residue(ResIdx(0)).name().value()

    solute = solute.edit().rename(lig_name).commit()

    perturbations_lib = PerturbationsLibrary(morphfile.val)
    solute = perturbations_lib.applyTemplate(solute)

    perturbations = solute.property("perturbations")

    lam = Symbol("lambda")

    initial = Perturbation.symbols().initial()
    final = Perturbation.symbols().final()

    solute = solute.edit().setProperty("perturbations",
                                       perturbations.recreate((1 - lam) * initial + lam * final)).commit()

    # We put atoms in three groups depending on what happens in the perturbation
    # non dummy to non dummy --> the hard group, uses a normal intermolecular FF
    # non dummy to dummy --> the todummy group, uses SoftFF with alpha = Lambda
    # dummy to non dummy --> the fromdummy group, uses SoftFF with alpha = 1 - Lambda
    # We start assuming all atoms are hard atoms. Then we call getDummies to find which atoms
    # start/end as dummies and update the hard, todummy and fromdummy groups accordingly

    solute_grp_ref = MoleculeGroup("solute_ref", solute)
    solute_grp_ref_hard = MoleculeGroup("solute_ref_hard")
    solute_grp_ref_todummy = MoleculeGroup("solute_ref_todummy")
    solute_grp_ref_fromdummy = MoleculeGroup("solute_ref_fromdummy")

    solute_ref_hard = solute.selectAllAtoms()
    solute_ref_todummy = solute_ref_hard.invert()
    solute_ref_fromdummy = solute_ref_hard.invert()

    to_dummies, from_dummies = getDummies(solute)

    if to_dummies is not None:
        ndummies = to_dummies.count()
        dummies = to_dummies.atoms()

        for x in range(0, ndummies):
            dummy_index = dummies[x].index()
            solute_ref_hard = solute_ref_hard.subtract(solute.select(dummy_index))
            solute_ref_todummy = solute_ref_todummy.add(solute.select(dummy_index))

    if from_dummies is not None:
        ndummies = from_dummies.count()
        dummies = from_dummies.atoms()

        for x in range(0, ndummies):
            dummy_index = dummies[x].index()
            solute_ref_hard = solute_ref_hard.subtract(solute.select(dummy_index))
            solute_ref_fromdummy = solute_ref_fromdummy.add(solute.select(dummy_index))

    solute_grp_ref_hard.add(solute_ref_hard)
    solute_grp_ref_todummy.add(solute_ref_todummy)
    solute_grp_ref_fromdummy.add(solute_ref_fromdummy)

    solutes = MoleculeGroup("solutes")
    solutes.add(solute)

    molecules = MoleculeGroup("molecules")
    molecules.add(solute)

    solvent = MoleculeGroup("solvent")

    #for molecule in moleculeList[1:]:
    for molecule in moleculeList:
        molecules.add(molecule)
        solvent.add(molecule)

    all = MoleculeGroup("all")

    all.add(molecules)
    all.add(solvent)

    all.add(solutes)
    all.add(solute_grp_ref)
    all.add(solute_grp_ref_hard)
    all.add(solute_grp_ref_todummy)
    all.add(solute_grp_ref_fromdummy)

    # Add these groups to the System
    system = System()

    system.add(solutes)
    system.add(solute_grp_ref)
    system.add(solute_grp_ref_hard)
    system.add(solute_grp_ref_todummy)
    system.add(solute_grp_ref_fromdummy)

    system.add(molecules)

    system.add(solvent)

    system.add(all)

    return system


def clearBuffers(system):
    r"""
    Parameters
    ----------
    system : Sire.system
        contains Sire system
    Returns
    -------
    system : Sire.system
        returns a
    """

    print ("Clearing buffers...")

    mols = system[MGName("all")].molecules()
    molnums = mols.molNums()

    changedmols = MoleculeGroup("changedmols")

    for molnum in molnums:
        mol = mols.molecule(molnum)[0].molecule()
        molprops = mol.propertyKeys()
        editmol = mol.edit()
        for molprop in molprops:
            if molprop.startswith("buffered_"):
                #print "Removing property %s " % molprop
                editmol.removeProperty(PropertyName(molprop))
        mol = editmol.commit()
        changedmols.add(mol)
        #system.update(mol)

    system.update(changedmols)

    return system

def getAllData(integrator, steps):
    gradients = integrator.getGradients()
    f_metropolis = integrator.getForwardMetropolis()
    b_metropolis = integrator.getBackwardMetropolis()
    energies = integrator.getEnergies()
    reduced_pot_en = integrator.getReducedPerturbedEnergies()
    outdata = None
    l = [len(gradients), len(f_metropolis), len(b_metropolis), len(energies), len(steps)]
    if len(set(l))!=1:
        print("Whoops somehow the data generated does not agree in their first dimensions...exiting now.")
        exit(-1)
    else:
        if len(gradients) == len(reduced_pot_en):
            outdata = np.column_stack((steps, energies, gradients,
                                   f_metropolis, b_metropolis,
                                   reduced_pot_en))
        elif len(reduced_pot_en)==0:
            outdata = np.column_stack((steps, energies, gradients,
                                   f_metropolis, b_metropolis))
            print("Warning: you didn't specify a lambda array, no reduced perturbed energies can be written to file.")
        else:
            print("Whoops somehow the data generated does not agree in their first dimensions...exiting now.")
            exit(-1)
    return outdata

def getAtomNearCOG( molecule ):

    mol_centre = molecule.evaluate().center()
    mindist = 99999.0

    for x in range(0, molecule.nAtoms()):
        atom = molecule.atoms()[x]
        at_coords = atom.property('coordinates')
        dist = Vector().distance2(at_coords, mol_centre)
        if dist < mindist:
            mindist = dist
            nearest_atom = atom

    return nearest_atom

def generateDistanceRestraintsDict(system):
    r"""
    Parameters
    ----------
    system : Sire.system
        contains Sire system
    Updates the contents of the Paramete distance_restraints_dict
    """
    # Step 1) Assume ligand is first solute
    # Find atom nearest to COG
    molecules = system.molecules()
    molnums = molecules.molNums()
    solute = molecules.at(MolNum(1))[0].molecule()
    nearestcog_atom = getAtomNearCOG( solute )
    icoord = nearestcog_atom.property("coordinates")
    # Step 2) Find nearest 'CA' heavy atom in other solutes (skip water  & ions)
    dmin = 9999999.0
    closest = None
    for molnum in molnums:
        molecule = molecules.molecule(molnum)[0].molecule()
        if molecule == solute:
            continue
        if molecule.residues()[0].name() == ResName("WAT"):
            continue
        #print (molecule)
        ca_atoms = molecule.selectAll(AtomName("CA"))
        for ca in ca_atoms:
            jcoord = ca.property("coordinates")
            d = Vector().distance(icoord,jcoord)
            if d < dmin:
                dmin = d
                closest = ca
    # Step 3) Compute position of 'mirror' CA. Find nearest CA atom to that point
    jcoord = closest.property("coordinates")
    mirror_coord = icoord-(jcoord-icoord)
    dmin = 9999999.0
    mirror_closest = None
    for molnum in molnums:
        molecule = molecules.molecule(molnum)[0].molecule()
        if molecule == solute:
            continue
        if molecule.residues()[0].name() == ResName("WAT"):
            continue
        #print (molecule)
        ca_atoms = molecule.selectAll(AtomName("CA"))
        for ca in ca_atoms:
            jcoord = ca.property("coordinates")
            d = Vector().distance(mirror_coord,jcoord)
            if d < dmin:
                dmin = d
                mirror_closest = ca
    #print (mirror_closest)
    # Step 4) Setup restraint parameters
    kl = 10.00 # kcal/mol/Angstrom^2
    Dl = 2.00 # Angstrom
    i0 = nearestcog_atom.index().value()
    i1 = closest.index().value()
    i2 = mirror_closest.index().value()
    r01 = Vector().distance(nearestcog_atom.property("coordinates"),closest.property("coordinates"))
    r02 = Vector().distance(nearestcog_atom.property("coordinates"),mirror_closest.property("coordinates"))
    restraints = { (i0, i1): (r01, kl, Dl), (i0,i2): (r02, kl, Dl) }
    #print restraints
    #distance_restraints_dict.val = restraints
    #distance_restraints_dict 
    
    return restraints

######## MAIN SCRIPTS  #############

@resolveParameters
def run():

    try:
        host = os.environ['HOSTNAME']
    except KeyError:
        host = "unknown"

    print("\n### Running Molecular Dynamics simulation on %s ###" % host)
    if verbose.val:
        print("###================= Simulation Parameters=====================###")
        Parameter.printAll()
        print ("###===========================================================###\n")

    timer = QTime()
    timer.start()

    # Setup the system from scratch if no restart file is available
    print("###================Setting up calculation=====================###")
    if not os.path.exists(restart_file.val):

        print("New run. Loading input and creating restart")

        amber = Amber()

        if os.path.exists(s3file.val):
            (molecules, space) = Sire.Stream.load(s3file.val)
        else:
            (molecules, space) = amber.readCrdTop(crdfile.val, topfile.val)
            Sire.Stream.save((molecules, space), s3file.val)

        system = createSystem(molecules)

        if center_solute.val:
            system = centerSolute(system, space)

        if use_restraints.val:
            system = setupRestraints(system)

        if use_distance_restraints.val:
            restraints = None
            if len(distance_restraints_dict.val) == 0:
                print ("Distance restraints have been activated, but none have been specified. Will autogenerate.")
                restraints = generateDistanceRestraintsDict(system)
                # Save restraints
                print ("Autogenerated distance restraints values: %s " % distance_restraints_dict)
                stream = open("restraints.cfg",'w')
                stream.write("distance restraints dictionary = %s\n" % restraints)
                stream.close()
            system = setupDistanceRestraints(system, restraints=restraints)

        if hydrogen_mass_repartitioning_factor.val is not None:
            system = repartitionMasses(system, hmassfactor=hydrogen_mass_repartitioning_factor.val)

        # Note that this just set the mass to zero which freezes residues in OpenMM but Sire doesn't known that
        if freeze_residues.val:
            system = freezeResidues(system)

        system = setupForcefields(system, space)

        if random_seed.val:
            ranseed = random_seed.val
        else:
            ranseed = RanGenerator().randInt(100000, 1000000)

        print("Setting up the simulation with random seed %s" % ranseed)

        moves = setupMoves(system, ranseed, gpu.val)
        MCmoves = setupMCmoves(system, ranseed)
        
        print("Saving restart")
        Sire.Stream.save([system, moves, MCmoves], restart_file.val)
    else:
        system, moves, MCmoves = Sire.Stream.load(restart_file.val)
        move0 = moves.moves()[0]
        integrator = move0.integrator()
        integrator.setDeviceIndex(str(gpu.val))
        move0.setIntegrator(integrator)
        moves = WeightedMoves()
        moves.add(move0)
        print("Index GPU = %s " % moves.moves()[0].integrator().getDeviceIndex())
        print("Loaded a restart file on which we have performed %d moves." % moves.nMoves())
        #Maybe include a runtime error here!
        if minimise.val:
            print ('WARNING: You are trying to minimise from a restart! Revise your config file!')
        if equilibrate.val:
            print ('WARNING: You are trying to equilibrate from a restart! Revise your config file!')

    #cycle_start = int(moves.nMoves() / nmoves.val) + 1
    cycle_start = 1
    cycle_end = cycle_start + ncycles.val

    if (save_coords.val):
        trajectory = setupDCD(system)

    mdmoves = moves.moves()[0]
    integrator = mdmoves.integrator()

    print ("###===========================================================###\n")

    if minimise.val:
        print("###=======================Minimisation========================###")
        print('Running minimisation.')
        if verbose.val:
            print ("Energy before the minimisation: " + str(system.energy()))
            print ('Tolerance for minimisation: ' + str(minimise_tol.val))
            print ('Maximum number of minimisation iterations: ' + str(minimise_max_iter.val))
        integrator.setConstraintType("none")
        system = integrator.minimiseEnergy(system, minimise_tol.val, minimise_max_iter.val)
        system.mustNowRecalculateFromScratch()
        if verbose.val:
            print ("Energy after the minimization: " + str(system.energy()))
            print ("Energy minimization done.")
        integrator.setConstraintType(constraint.val)
        print("###===========================================================###\n", flush=True)

    if equilibrate.val:
        print("###======================Equilibration========================###")
        print ('Running equilibration.')
        # Here we anneal lambda (To be determined)
        if verbose.val:
            print ('Equilibration timestep ' + str(equil_timestep.val))
            print ('Number of equilibration steps: ' + str(equil_iterations.val))
        system = integrator.equilibrateSystem(system, equil_timestep.val, equil_iterations.val)
        system.mustNowRecalculateFromScratch()
        if verbose.val:
            print ("Energy after the equilibration: " + str(system.energy()))
            print ('Equilibration done.\n')
        print("###===========================================================###\n", flush=True)

    simtime=nmoves.val*ncycles.val*timestep.val
    print("###=======================somd run============================###")
    print ("Starting somd run...")
    print ("%s moves %s cycles, %s simulation time" %(nmoves.val, ncycles.val, simtime))

    s1 = timer.elapsed() / 1000.
    avg_nrg = 0.0
    count = 0
    molNums = system.molNums()
    #PDB().write(system.molecules(),"begin.pdb")
    #print (system.energy())
    for i in range(cycle_start, cycle_end):
        print("\nCycle = ", i, flush=True )
        #PDB().write(system.molecules(),"before.pdb")
        #print (system.energy())
        system = MCmoves.move(system, nmcmoves.val, True)
        #PDB().write(system1.molecules(),"after.pdb")
        #print (system1.energy())
        #import pdb; pdb.set_trace()
        #sys.exit(-1)
        # preserve velocities 
        #for molnum in molNums:
        #    mol0 = system.molecule(molnum)[0].molecule()
        #    mol1 = system1.molecule(molnum)[0].molecule()
        #    if (not mol1.hasProperty("velocity") and mol0.hasProperty("velocity")):
        #        vel0 = mol0.property("velocity")
        #        mol1 = mol1.edit().setProperty("velocity", vel0).commit()
        #        system1.update(mol1)
        #system = system1
        system = moves.move(system, nmoves.val, True)
        print("\npot. energy = ", system.energy(), flush=True)
        avg_nrg += system.energy().value()
        count += 1
        # what do I write if previous move was MC ?
        if (save_coords.val):
            writeSystemData(system, [moves, MCmoves], trajectory, i)
            
    s2 = timer.elapsed() / 1000.
    print("Simulation took %d s " % ( s2 - s1))
    print ("Average pot energy %8.5f " % (avg_nrg/count))
    print("Saving restart")
    Sire.Stream.save([system, moves, MCmoves], restart_file.val)
    #print (system.monitor(MonitorName('total_energy')).accumulator().average())
    #import pdb; pdb.set_trace()

if __name__ == '__main__':
    topfile = Parameter("topfile","input/lig2.prm7","")
    crdfile = Parameter("crdfile","input/lig2.rst7","")
    LIGAND_FLEX_FILE = "input/lig2.flex"
    #topfile = Parameter("topfile","input/n2.prm7","")
    #crdfile = Parameter("crdfile","input/n2.rst7","")
    #LIGAND_FLEX_FILE = "input/n2.flex"   
    # Note cannot set MCMOVE_WEIGHT to 0 as this set an exception
    # because Sire thinks the MD move only samples NVE.
    # could be fixed by updating openmmmdintegrator.
    # for now setting MDMOVE >> MCMOVE will cause very few MC moves to be attempted
    LIGAND_NAME = "LIG"
    LIGAND_NUM = 1
    run()
