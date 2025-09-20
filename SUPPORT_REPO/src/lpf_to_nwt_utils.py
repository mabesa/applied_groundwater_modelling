import flopy
import numpy as np

def convert_modflow2005_to_nwt(mf2005, new_model_name="limmat_valley_nwt"):
    """
    Convert existing MODFLOW-2005 model to MODFLOW-NWT.
    
    Parameters:
    -----------
    mf2005 : flopy.modflow.Modflow
        Existing MODFLOW-2005 model object
    new_model_name : str
        Name for the new MODFLOW-NWT model
    
    Returns:
    --------
    flopy.modflow.ModflowNwt
        New MODFLOW-NWT model object
    """
    
    print("Converting existing MODFLOW-2005 model to NWT...")

    # Create a new model object for MODFLOW-NWT
    mf_nwt = flopy.modflow.Modflow(
        new_model_name, 
        model_ws=mf2005.model_ws,
        version='mfnwt', 
        exe_name='mfnwt.exe'
    )
    
    print("Creating new MODFLOW-NWT model...")
    
    
    # 1. Copy DIS package (usually unchanged)
    print("Copying DIS package...")
    dis_old = mf2005.get_package('DIS')
    dis_new = flopy.modflow.ModflowDis(
        mf_nwt,
        nlay=dis_old.nlay,
        nrow=dis_old.nrow,
        ncol=dis_old.ncol,
        delr=dis_old.delr.array,
        delc=dis_old.delc.array,
        top=dis_old.top.array,
        botm=dis_old.botm.array,
        nper=dis_old.nper,
        perlen=dis_old.perlen,
        nstp=dis_old.nstp,
        steady=dis_old.steady
    )
    
    # 2. Convert BAS to BAS6 (usually unchanged)
    print("Copying BAS6 package...")
    bas_old = mf2005.get_package('BAS6')
    bas_new = flopy.modflow.ModflowBas(
        mf_nwt,
        ibound=bas_old.ibound.array,
        strt=bas_old.strt.array,
        hnoflo=bas_old.hnoflo
    )
    
    # 3. Convert LPF to UPW (main difference for unconfined)
    print("Converting LPF to UPW package...")
    lpf_old = mf2005.get_package('LPF')
    
    # UPW package for MODFLOW-NWT
    upw_new = flopy.modflow.ModflowUpw(
        mf_nwt,
        laytyp=lpf_old.laytyp,  # Keep layer types
        layavg=lpf_old.layavg,  # Keep averaging method
        chani=lpf_old.chani,    # Keep anisotropy
        layvka=lpf_old.layvka,  # Keep VK flag
        laywet=0,               # NWT handles wetting internally
        hk=lpf_old.hk.array,    # Horizontal K
        vka=lpf_old.vka.array if lpf_old.vka is not None else lpf_old.hk.array,  # Vertical K
        ss=lpf_old.ss.array if lpf_old.ss is not None else 1e-5,  # Specific storage
        sy=lpf_old.sy.array if lpf_old.sy is not None else 0.2,   # Specific yield
        # Remove wetdry - NWT doesn't use it
    )
    
    # 4. Replace PCG with NWT solver
    print("Adding NWT solver...")
    nwt = flopy.modflow.ModflowNwt(
        mf_nwt,
        headtol=0.01,          # Less strict than PCG for stability
        fluxtol=500,           # Flux tolerance
        maxiterout=100,        # Outer iterations
        thickfact=1e-5,        # Thin cell factor
        linmeth=1,             # Linear solver method (1=GMRES, 2=XMD)
        iprnwt=0,              # Print flag
        ibotav=0,              # Bottom averaging
        options='COMPLEX',     # Use complex option for better convergence
        Continue=False         # Don't continue on non-convergence
    )
    
    # 5. Copy boundary condition packages (unchanged)
    print("Copying boundary condition packages...")
    
    # CHD package
    chd_old = mf2005.get_package('CHD')
    if chd_old is not None:
        chd_new = flopy.modflow.ModflowChd(
            mf_nwt,
            stress_period_data=chd_old.stress_period_data
        )
    
    # WEL package
    wel_old = mf2005.get_package('WEL')
    if wel_old is not None:
        wel_new = flopy.modflow.ModflowWel(
            mf_nwt,
            stress_period_data=wel_old.stress_period_data
        )
    
    # RIV package
    riv_old = mf2005.get_package('RIV')
    if riv_old is not None:
        riv_new = flopy.modflow.ModflowRiv(
            mf_nwt,
            stress_period_data=riv_old.stress_period_data
        )
    
    # RCH package
    rch_old = mf2005.get_package('RCH')
    if rch_old is not None:
        rech_array = rch_old.rech.array
        # Remove singleton dimensions
        rech_array = np.squeeze(rech_array)
        # If still 3D (nper, nrow, ncol), and nper=1, reduce to 2D
        if rech_array.ndim == 3 and rech_array.shape[0] == 1:
            rech_array = rech_array[0]
        rch_new = flopy.modflow.ModflowRch(
            mf_nwt,
            rech=rech_array,
            nrchop=rch_old.nrchop
    )
    
    # 6. Copy output control
    print("Copying OC package...")
    oc_old = mf2005.get_package('OC')
    if oc_old is not None:
        oc_new = flopy.modflow.ModflowOc(
            mf_nwt,
            stress_period_data=oc_old.stress_period_data,
            cboufm='(20i5)',
            compact=True
        )
    
    print(f"MODFLOW-NWT model created: {new_model_name}")
    return mf_nwt

def create_nwt_from_scratch(existing_model):
    """
    Alternative approach: Create MODFLOW-NWT model using data from existing model.
    Use this if the conversion function doesn't work perfectly.
    """
    
    # Get key data from existing model
    dis = existing_model.get_package('DIS')
    bas = existing_model.get_package('BAS6')
    lpf = existing_model.get_package('LPF')
    
    # Create new NWT model
    mf_nwt = flopy.modflow.ModflowNwt(
        modelname="limmat_valley_nwt",
        exe_name='mfnwt.exe'
    )
    
    # Add packages step by step with careful attention to thin layers
    
    # DIS package
    dis_nwt = flopy.modflow.ModflowDis(
        mf_nwt,
        nlay=dis.nlay,
        nrow=dis.nrow,
        ncol=dis.ncol,
        delr=dis.delr.array,
        delc=dis.delc.array,
        top=dis.top.array,
        botm=dis.botm.array,
        nper=dis.nper,
        perlen=dis.perlen,
        nstp=dis.nstp,
        steady=dis.steady
    )
    
    # BAS package
    bas_nwt = flopy.modflow.ModflowBas(
        mf_nwt,
        ibound=bas.ibound.array,
        strt=bas.strt.array,
        hnoflo=bas.hnoflo
    )
    
    # UPW package (replaces LPF)
    upw_nwt = flopy.modflow.ModflowUpw(
        mf_nwt,
        laytyp=1,  # Convertible (unconfined)
        layavg=0,  # Harmonic averaging
        chani=1.0, # Horizontal anisotropy
        layvka=0,  # VKA is vertical K
        laywet=0,  # No wetting (NWT handles internally)
        hk=lpf.hk.array,
        vka=lpf.vka.array if lpf.vka is not None else lpf.hk.array * 0.1,
        ss=1e-5,   # Specific storage
        sy=0.2,    # Specific yield
    )
    
    # NWT solver - optimized for thin layers
    nwt = flopy.modflow.ModflowNwt(
        mf_nwt,
        headtol=0.01,          # Relaxed head tolerance
        fluxtol=500,           # Flux tolerance
        maxiterout=200,        # More outer iterations
        thickfact=1e-5,        # Minimum saturated thickness factor
        linmeth=1,             # GMRES solver
        iprnwt=1,              # Print convergence info
        ibotav=1,              # Average cell bottom elevations
        options='SIMPLE',      # Start with SIMPLE, upgrade to COMPLEX if needed
        Continue=False,
        dbdtheta=0.9,         # Theta for backward differences
        dbdkappa=1e-5,        # Kappa for backward differences
        dbdgamma=0.0,         # Gamma for backward differences
        momfact=0.1,          # Momentum factor
        backflag=1,           # Backtracking flag
        maxbackiter=50,       # Max backtracking iterations
        backtol=1.1,          # Backtracking tolerance
        backreduce=0.7,       # Backtracking reduction factor
    )
    
    return mf_nwt

def optimize_nwt_for_thin_layers(mf_nwt):
    """
    Apply specific optimizations for thin layer problems.
    """
    
    print("Applying thin layer optimizations...")
    
    # Get the NWT package and modify settings
    nwt_pkg = mf_nwt.get_package('NWT')
    
    # Recommended settings for thin layers and extensive drying
    nwt_pkg.headtol = 0.1        # Very relaxed head tolerance
    nwt_pkg.fluxtol = 1000       # Relaxed flux tolerance
    nwt_pkg.thickfact = 1e-4     # Slightly larger minimum thickness
    nwt_pkg.options = 'COMPLEX'  # Use complex option for difficult problems
    nwt_pkg.linmeth = 2          # Try XMD solver instead of GMRES
    nwt_pkg.Continue = True      # Continue even if not fully converged
    
    # Consider reducing pumping rates initially
    wel_pkg = mf_nwt.get_package('WEL')
    if wel_pkg is not None:
        print("Consider reducing well pumping rates by 50% initially...")
        # wel_pkg.stress_period_data[0]['flux'] *= 0.5  # Uncomment to reduce pumping

