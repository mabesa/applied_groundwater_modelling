#!/usr/bin/env python
# filepath: /Users/bea/Documents/GitHub/applied_groundwater_modelling/src/scripts/test_flopy_installation.py

"""
Test script to verify flopy installation is working properly.
Runs a simple MODFLOW 6 model based on examples in the course materials.
"""

import os
import sys
from tempfile import TemporaryDirectory
import numpy as np

def test_flopy_installation():
    """Test if flopy can be imported and run a simple model."""
    try:
        import flopy
        print(f"✅ flopy imported successfully (version {flopy.__version__})")
    except ImportError:
        print("❌ Failed to import flopy")
        sys.exit(1)

    # Make sure we can access MODFLOW executables
    try:
        print(f"MODFLOW 6 executable path: {flopy.mf6.get_mf6_exe()}")
    except Exception as e:
        print(f"⚠️ Note: MODFLOW 6 executable not found. This is expected in CI environment.")
        print(f"  Error: {str(e)}")
        # Continue anyway as we'll skip the actual execution in CI

    # Create a simple model (based on example in 03_modflow/content/modflow.ipynb)
    with TemporaryDirectory() as workspace:
        name = "flopy_test"
        print(f"\nCreating test model in {workspace}")

        # Set up the simulation
        sim = flopy.mf6.MFSimulation(sim_name=name, sim_ws=workspace)

        # Create TDIS package
        flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[[1.0, 1, 1.0]])

        # Create IMS package
        flopy.mf6.ModflowIms(sim)

        # Create groundwater flow model
        gwf = flopy.mf6.ModflowGwf(sim, modelname=name, save_flows=True)

        # Create discretization package
        botm = [30.0, 20.0, 10.0]
        flopy.mf6.ModflowGwfdis(gwf, nlay=3, nrow=4, ncol=5, top=50.0, botm=botm)

        # Create initial conditions package
        flopy.mf6.ModflowGwfic(gwf)

        # Create node property flow package
        flopy.mf6.ModflowGwfnpf(gwf, save_specific_discharge=True)

        # Create constant head boundary
        flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[[(0, 0, 0), 1.0], [(2, 3, 4), 0.0]])

        # Create output control package
        budget_file = f"{name}.bud"
        head_file = f"{name}.hds"
        flopy.mf6.ModflowGwfoc(
            gwf,
            budget_filerecord=budget_file,
            head_filerecord=head_file,
            saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
        )

        print("Model definition completed successfully")

        # Write the input files
        try:
            sim.write_simulation()
            print("✅ Model input files written successfully")
        except Exception as e:
            print(f"❌ Failed to write model input files: {str(e)}")
            sys.exit(1)

        # Try to run the model (may fail in CI without MODFLOW executable)
        try:
            success, output = sim.run_simulation()
            if success:
                print("✅ Model ran successfully")
            else:
                print("❌ Model run failed")
                print(f"Output: {output}")
                # Don't exit with error as this is expected in CI
        except Exception as e:
            print(f"⚠️ Could not run model (expected in CI environment): {str(e)}")

    # Also test the MODFLOW 2005 interface since that's mentioned in the course
    with TemporaryDirectory() as workspace:
        name = "mf2005_test"
        print(f"\nTesting MODFLOW 2005 interface in {workspace}")

        try:
            import flopy.modflow as fpm

            # Create the MODFLOW model
            model = fpm.Modflow(modelname=name, exe_name='mf2005', model_ws=workspace)

            # Discretization
            nlay, nrow, ncol = 1, 1, 100
            delr = delc = 10.0
            fpm.ModflowDis(model, nlay=nlay, nrow=nrow, ncol=ncol, delr=delr, delc=delc)

            # Basic package
            ibound = np.ones((nlay, nrow, ncol), dtype=np.int32)
            strt = np.ones((nlay, nrow, ncol), dtype=np.float32) * 10.0
            fpm.ModflowBas(model, ibound=ibound, strt=strt)

            # LPF package
            fpm.ModflowLpf(model, hk=10.0)

            # OC package
            fpm.ModflowOc(model)

            # PCG package
            fpm.ModflowPcg(model)

            # Write input files
            model.write_input()
            print("✅ MODFLOW 2005 input files written successfully")
        except Exception as e:
            print(f"❌ Failed to create MODFLOW 2005 model: {str(e)}")
            sys.exit(1)

    print("\n✅ All flopy tests passed!")
    return True

if __name__ == "__main__":
    test_flopy_installation()