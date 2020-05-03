# Reconstruction using quadratic estimator
import numpy as np
import healpy as hp
import pickle

# from cmblensplus/wrap
import curvedsky
import basic

# from cmblensplus/utils
import quad_func
import misctools

# local
import prjlib


def init_quad(ids,stag,**kwargs):

    # setup parameters for lensing reconstruction (see cmblensplus/utils/quad_func.py)
    qtau = quad_func.quad(qlist=['TT'],qtype='tau',**kwargs)
    qlen = quad_func.quad(qlist=['TT'],qtype='lens',**kwargs)
    qsrc = quad_func.quad(qlist=['TT'],qtype='src',**kwargs)
    qtbh = quad_func.quad(qlist=['TT'],qtype='tau',**kwargs)
    qtBH = quad_func.quad(qlist=['TT'],qtype='tau',**kwargs)

    d = prjlib.data_directory()

    quad_func.quad.fname(qtau,d['root'],ids,stag)
    quad_func.quad.fname(qlen,d['root'],ids,stag)
    quad_func.quad.fname(qsrc,d['root'],ids,stag)
    quad_func.quad.fname(qtbh,d['root'],ids,'bh_'+stag)
    quad_func.quad.fname(qtBH,d['root'],ids,'BH_'+stag)

    return qtau, qlen, qsrc, qtbh, qtBH



def aps(rlz,qobj,fklm=None,q='TT',**kwargs_ov):

    for i in rlz:
        
        if misctools.check_path(qobj.f[q].cl[i],**kwargs_ov): continue
        if kwargs_ov['verbose']:  misctools.progress(i,rlz,text='Current progress',addtext='(qrec aps)')
        
        # load qlm
        alm = pickle.load(open(qobj.f[q].alm[i],"rb"))[0]
        mf  = pickle.load(open(qobj.f[q].mfb[i],"rb"))[0]
        alm -= mf

        # flip sign as e^-tau ~ 1-tau
        if qobj.qtype == 'tau':
            alm = -alm
        
        # auto spectrum
        cl = np.zeros((3,qobj.olmax+1))
        cl[0,:] = curvedsky.utils.alm2cl(qobj.olmax,alm)/qobj.wn[4]

        if fklm is not None and i>0:
            # load input klm
            if qobj.qtype == 'lens':
                iKlm = hp.fitsfunc.read_alm(fklm[i])
                iklm = curvedsky.utils.lm_healpy2healpix(len(iKlm),iKlm,2048)        
            if qobj.qtype == 'tau':
                iklm = pickle.load(open(fklm[i],"rb"))
            if qobj.qtype == 'src':
                iklm = 0.*alm
            # cross with input
            cl[1,:] = curvedsky.utils.alm2cl(qobj.olmax,alm,iklm)/qobj.wn[2]
            # input
            cl[2,:] = curvedsky.utils.alm2cl(qobj.olmax,iklm)

        np.savetxt(qobj.f[q].cl[i],np.concatenate((qobj.l[None,:],cl)).T)


def qrec_bh_tau(qtau,qlen,qsrc,qtbh,rlz,q='TT',est=['lens','tau','src'],**kwargs_ov):

    At = np.loadtxt(qtau.f[q].al,unpack=True)[1]

    # calculate response function
    Btt, Btg, Bts = quad_func.quad.coeff_bhe(qtau,est=est,qcomb=q,gtype='k')
    if not misctools.check_path(qtbh.f[q].al,**kwargs_ov):
        np.savetxt(qtbh.f[q].al,np.array((qtau.l,At*Btt,At)).T)

    # calculate bh-estimator 
    for i in rlz:
        
        if misctools.check_path(qtbh.f[q].alm[i],**kwargs_ov): continue
        if kwargs_ov['verbose']:  misctools.progress(i,rlz,text='Current progress',addtext='(qrec_bh_tau)')

        tlm = pickle.load(open(qtau.f[q].alm[i],"rb"))[0]
        glm = pickle.load(open(qlen.f[q].alm[i],"rb"))[0]
        if 'src' in est: 
            slm = pickle.load(open(qsrc.f[q].alm[i],"rb"))[0]
        else:
            slm = 0.*glm

        alm = Btt[:,None]*tlm + Btg[:,None]*glm + Bts[:,None]*slm
        pickle.dump((alm,alm*0.),open(qtbh.f[q].alm[i],"wb"),protocol=pickle.HIGHEST_PROTOCOL)

    quad_func.quad.mean_rlz(qtbh,rlz,**kwargs_ov)



def interface(qrun=['norm','qrec','n0','mean'],run=['tau','len','tbh'],kwargs_ov={},kwargs_cmb={},kwargs_qrec={},ep=1e-30):
    
    p = prjlib.init_analysis(**kwargs_cmb)
    __, __, wn = prjlib.set_mask(p.famask)

    # load obscls
    if p.fltr == 'none':
        ocl = np.loadtxt(p.fcmb.scl,unpack=True)[4:5]
        ifl = ocl.copy()

    if p.fltr == 'cinv':
        bl  = np.loadtxt(p.fbeam)[:p.lmax+1]
        cnl = p.lcl[0,:] + (1./bl)**2*(30.*np.pi/10800./2.72e6)**2
        wcl = np.loadtxt(p.fcmb.scl,unpack=True)[4]

        # quality factor defined in Planck 2015 lensing paper
        Ql  = (p.lcl[0,:])**2/(wcl*cnl+ep**2)
        # T' = QT^f = Q/(cl+nl) * (T+n)/sqrt(Q)

        ocl = cnl/(Ql+ep)  # corrected observed cl
        ifl = p.lcl[0,:]/(Ql+ep)    # remove theory signal cl in wiener filter
        ocl = np.reshape(ocl,(1,p.lmax+1))
        ifl = np.reshape(ifl,(1,p.lmax+1))

        wn[:] = wn[0]

    # define objects
    qtau, qlen, qsrc, qtbh, qtBH = init_quad(p.ids,p.stag,wn=wn,lcl=p.lcl,ocl=ocl,ifl=ifl,falm=p.fcmb.alms['c'],**kwargs_qrec)

    # reconstruction
    if 'tau' in run:
        quad_func.qrec_flow(qtau,p.rlz,run=qrun,**kwargs_ov)  #tau rec
        if 'aps' in qrun:  aps(p.rlz,qtau,fklm=p.ftalm,**kwargs_ov)

    if 'len' in run:
        quad_func.qrec_flow(qlen,p.rlz,run=qrun,**kwargs_ov)  #lens rec
        if 'aps' in qrun:  aps(p.rlz,qlen,fklm=p.fiklm,**kwargs_ov)

    if 'src' in run:
        quad_func.qrec_flow(qsrc,p.rlz,run=qrun,**kwargs_ov)  #src rec
        if 'aps' in qrun:  aps(p.rlz,qsrc,fklm=p.ftalm,**kwargs_ov)

    if 'tbh' in run:
        qrec_bh_tau(qtau,qlen,qsrc,qtbh,p.rlz,est=['lens','tau'],**kwargs_ov)  #BHE for tau
        if 'aps' in qrun:  aps(p.rlz,qtbh,fklm=p.ftalm,**kwargs_ov)

    if 'tBH' in run:
        qrec_bh_tau(qtau,qlen,qsrc,qtBH,p.rlz,est=['lens','tau','src'],**kwargs_ov)  #full BHE for tau
        if 'aps' in qrun:  aps(p.rlz,qtBH,fklm=p.ftalm,**kwargs_ov)


