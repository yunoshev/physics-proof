from helpers import physics
import math
# option width
mpp_bp, sig_bp = physics.scale_from_reference(52.0, 2.0, 0.5207, 0.03)
print('bpw',mpp_bp,sig_bp)
mpp_p, sig_p = physics.scale_from_reference(130.0, 4.0, 1.71, 0.20)
print('person stand',mpp_p,sig_p)
diff=abs(mpp_bp-mpp_p); comb=math.sqrt(sig_bp**2+sig_p**2)
print(diff,2*comb,diff<=2*comb)
# option height bp 66 vs person 152 ext
mpp_bp2, sig_bp2 = physics.scale_from_reference(66.0, 2.0, 0.66, 0.03)
mpp_p2, sig_p2 = physics.scale_from_reference(152.0, 4.0, 1.71, 0.20)
print('bph',mpp_bp2,sig_bp2,'p ext',mpp_p2,sig_p2)
print(abs(mpp_bp2-mpp_p2),2*math.sqrt(sig_bp2**2+sig_p2**2))
