"""controllerd and the RP2040 HUD controller: dimming from the ambient sensor, the cell's thermal model with derate and
cut-off, and the sun-watch rule that closes the shutter when the sun is inside the ray-traced entry patch.
Ported from the 3-D simulator (hud.js updateLuminance / updateSun / updateThermal)."""
import math

import numpy as np

from . import plan as PL


class Controller:
    def __init__(self, settings):
        self.S = settings
        self.duty = 1.0
        self.lum = dict(Leye=0.0, Lpanel=0.0, contrast_sky=1.0, contrast_road=1.0, black=0.0, lux=0.0, path=PL.PATH_WS,
                        src=PL.PGU_SOURCES[2])
        self.cell = 32.0
        self.T1, self.T2 = 60.0, 70.0           # derate and cut-off thresholds (simulation values, ASSUMED)
        self.thermal = "ok"
        self.shutter = 1.0
        self.shutter_target = 1.0
        self.shutter_reason = ""
        self.sun = dict(in_patch=False, d_az=0.0, d_el=0.0, elev=0.0)
        self.power_off = False

    def source(self):
        S = self.S
        if S["window"] == "stage1":
            return dict(key="yod", label="YODOIT monitor via the 30% combiner", panel=1200.0)
        return next((s for s in PL.PGU_SOURCES if s["key"] == S["pgu"]), PL.PGU_SOURCES[2])

    def update(self, dt, env_key, sun_dir_car):
        S = self.S
        E = PL.ENVIRONMENTS[env_key]
        src = self.source()
        path = PL.PATH_COMB if S["window"] == "stage1" else (PL.PATH_WS_TWO if S["both_surfaces"] else PL.PATH_WS)
        Lmax = src["panel"] * path
        lux = E["lux"]
        # dimming curve: night ceiling (50 cd/m2 at the eye) at <= 10 lux, full at >= 10,000 lux, log-linear between
        night_duty = min(1.0, PL.L_NIGHT_EYE / Lmax)
        f = min(1.0, max(0.0, (math.log10(max(lux, 1.0)) - 1) / 3))
        target = math.exp(math.log(night_duty) * (1 - f)) if S["auto_dim"] else 1.0
        target = min(1.0, max(0.002, target * 1.25 ** S["dim_steps"]))
        if self.thermal == "derate":
            target *= 0.5
        if self.thermal == "cutoff":
            target = 0.0
        self.duty += (target - self.duty) * (1 - math.exp(-dt / 0.35))   # 1 s ramp
        L = self.lum
        L.update(lux=lux, path=path, src=src, Lpanel=src["panel"] * self.duty, Leye=Lmax * self.duty)
        L["contrast_sky"] = (L["Leye"] + E["L_sky"]) / E["L_sky"]
        L["contrast_road"] = (L["Leye"] + E["L_road"]) / E["L_road"]
        L["black"] = L["Leye"] / PL.CR_PANEL
        self._sun(dt, sun_dir_car)
        self._thermal(dt)

    def _sun(self, dt, sd):
        entry = np.array(PL.ENTRY_DIR, float)
        entry /= np.linalg.norm(entry)
        s = self.sun
        if sd is not None and sd[2] > 0:
            el = math.asin(max(-1, min(1, sd[2])))
            elE = math.asin(entry[2])
            az, azE = math.atan2(sd[1], sd[0]), math.atan2(entry[1], entry[0])
            d_az = (az - azE + math.pi) % (2 * math.pi) - math.pi
            s.update(d_az=math.degrees(d_az), d_el=math.degrees(el - elE), elev=math.degrees(el))
            s["in_patch"] = (abs(s["d_az"]) * math.cos(el) <= PL.PATCH_W / 2 and abs(s["d_el"]) <= PL.PATCH_H / 2)
        else:
            s["in_patch"] = False
            s["elev"] = math.degrees(math.asin(max(-1, min(1, sd[2])))) if sd is not None else -10.0
        self.shutter_target, self.shutter_reason = 1.0, ""
        if self.S["sun_watch"] and s["in_patch"]:
            self.shutter_target, self.shutter_reason = 0.0, "sun-watch"
        if self.thermal == "cutoff":
            self.shutter_target, self.shutter_reason = 0.0, "cell too hot"
        if self.power_off:
            self.shutter_target, self.shutter_reason = 0.0, "HUD off"
        rate = dt / 0.6                                        # servo travel about 0.6 s
        self.shutter += max(-rate, min(rate, self.shutter_target - self.shutter))

    def _thermal(self, dt):
        # cabin 30 C + backlight absorption (about 3 W at full, +24 C) + focused sun when the shutter is open
        sun_load = self.shutter * 95.0 if self.sun["in_patch"] else 0.0
        src = self.lum["src"]
        target = 30 + 24 * self.duty * min(1.0, src["panel"] / 10000.0) + sun_load
        self.cell += (target - self.cell) * (1 - math.exp(-dt / 20.0))
        self.thermal = "cutoff" if self.cell > self.T2 else "derate" if self.cell > self.T1 else "ok"

    # Display mapping. MetaDrive draws the road at about sRGB 0.65 under the noon light; the exposure layer then
    # multiplies the scene by E['scene']. That road stands for the adapting luminance L_adapt.
    ROAD_SRGB = 0.65

    def background_lin(self, env_key):
        """Linear display level of a background at the adapting luminance in this scene."""
        E = PL.ENVIRONMENTS[env_key]
        return (self.ROAD_SRGB * E["scene"]) ** 2.2

    def overlay_gain(self, env_key):
        """Linear gain for the virtual image: a full-white pixel adds Leye / L_adapt of the background's level.
        Polarised sunglasses pass almost none of the s-polarised image (a few per cent, ASSUMED)."""
        E = PL.ENVIRONMENTS[env_key]
        g = self.lum["Leye"] / E["L_adapt"] * self.background_lin(env_key) * self.shutter
        if self.S["sunglasses"]:
            g *= 0.03
        return g

    def black_gain(self, env_key):
        E = PL.ENVIRONMENTS[env_key]
        g = self.lum["black"] / E["L_adapt"] * self.background_lin(env_key) * self.shutter
        return g * (0.03 if self.S["sunglasses"] else 1.0)
