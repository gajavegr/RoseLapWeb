import numpy as np
import math

from constants import *
import logging

"""
Point mass model
It's a unicycle! Fast, right?
Even faster with steady state assumptions
"""

def derate_curvature(curv, raddl):
  return curv/(1.0 + raddl*curv)

def floor_sqrt(x):
  """
  Like sqrt but with a floor. If x <= 0, return 0.
  """
  if x > 0:
    return math.sqrt(x)
  return 0

def frem_filter(x):
  if np.isnan(x) or np.isinf(x):
    return 0
  return x

class sim_ss_onetire:
  def __init__(self):
    pass

  def brake(self, vehicle, sector, t0, xf, v0, vf, dl=0.1):
    n = int(sector.length/dl)
    channels = np.zeros((n, O_MATRIX_COLS))
    v = vf
    t = 0
    x = xf
    success = False
    for i in reversed(range(n)):
      a_lat = v**2 * derate_curvature(sector.curvature, vehicle.r_add)
      F_tire_lat = vehicle.mass * a_lat

      F_tire_long_available_FULL = vehicle.f_long_remain(4, vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_FULL), F_tire_lat)[0]
      F_tire_long_available_BRK = vehicle.f_long_remain(4, vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_BRK), F_tire_lat)[0]
      F_longitudinal_FULL = - F_tire_long_available_FULL - vehicle.drag(v, AERO_FULL)
      F_longitudinal_BRK = - F_tire_long_available_FULL - vehicle.drag(v, AERO_BRK)

      F_tire_long_available = F_tire_long_available_FULL
      F_longitudinal = F_longitudinal_FULL
      aero_mode = AERO_FULL
      N = vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_FULL)
      if (not success) and (F_longitudinal_FULL > F_longitudinal_BRK):
        # print('AIRBRAKE!')
        aero_mode = AERO_BRK
        F_tire_long_available = F_tire_long_available_BRK
        F_longitudinal = F_longitudinal_BRK
        N = vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_BRK)

      status = S_BRAKING
    
      
      a_long = F_longitudinal / vehicle.mass
      v = floor_sqrt(v**2 - 2*a_long*dl)

      if success:
        status = S_SUSTAINING
        aero_mode = AERO_FULL
        v = v0
      elif v > v0:
        # print('Sucessful brake from %.3f -> %.3f' % (v0,vf))
        success = True
        aero_mode = AERO_FULL
        v = v0

      t -= 1000 if v==0 else dl/v
      x -= dl

      channels[i,O_TIME]     = t
      channels[i,O_DISTANCE] = x
      channels[i,O_VELOCITY] = v
      channels[i,O_NR]       = N
      channels[i,O_SECTORS]  = sector.i
      channels[i,O_STATUS]   = status
      channels[i,O_GEAR]     = np.nan
      channels[i,O_LONG_ACC] = a_long/vehicle.g
      channels[i,O_LAT_ACC]  = a_lat/vehicle.g
      channels[i,O_FR_REMAINING] = 0
      channels[i,O_CURVATURE] = sector.curvature
      channels[i,O_ENG_RPM]   = np.nan
      channels[i,O_CO2] = 0
      channels[i,O_AERO_MODE] = aero_mode
      if success and i > 2:
        channels[i,O_STATUS] = S_SUSTAINING
        channels[:i,:] = np.tile(channels[i,:], (i,1))
        for j in reversed(range(0,i)):
          t -= dl/v
          x -= dl
          channels[j,O_TIME] = t
          channels[j,O_DISTANCE] = x
        break

    # if not success:
    #   print('Unsuccessful brake from %.3f -> %.3f (only hit %.3f)' % (v0,vf,channels[0,O_VELOCITY]))

    for i in range(n):
      channels[i,O_TIME] += t0 - t
    return channels, success

  def drive(self, vehicle, sector, x0, t0, v0, vf, vmax, gear=None, dl=0.1, start=False):
    n = int(sector.length / dl)
    channels = np.zeros((n, O_MATRIX_COLS))

    # perform forward integration to the end
    v = v0
    t = t0
    x = x0
    if np.isnan(gear):
      gear = vehicle.best_gear(v, np.inf)
    topped = False
    t_shift = -1
    v_shift = -1
    for i in range(n):
      # print(x,v)
      a_lat = v**2 * derate_curvature(sector.curvature, vehicle.r_add)
      F_tire_lat = vehicle.mass * a_lat

      best_gear = vehicle.best_gear(v, np.inf)
      if best_gear != gear and v > v_shift:
        gear += (best_gear-gear)/abs(best_gear-gear)
        t_shift = t+vehicle.shift_time
        v_shift = v*1.01
      F_tire_engine_limit, eng_rpm = vehicle.eng_force(v, int(gear))
      
      status = S_TOPPED_OUT

      aero_mode = AERO_DRS
      N = vehicle.mass*vehicle.g + vehicle.downforce(v, aero_mode)
      F_tire_long_available = vehicle.f_long_remain(4, N, F_tire_lat)[0]
      if F_tire_long_available < F_tire_engine_limit:
        aero_mode = AERO_FULL
        N = vehicle.mass*vehicle.g + vehicle.downforce(v, aero_mode)
        F_tire_long_available = vehicle.f_long_remain(4, N, F_tire_lat)[0]

      if t < t_shift:
        ### CURRENTLY SHIFTING, NO POWER! ### 
        status = S_SHIFTING
        F_tire_long = 0
      else:
        if t_shift > 0:
          t_shift = -1

        F_tire_long = F_tire_engine_limit
        status = S_ENG_LIM_ACC

        if F_tire_long > F_tire_long_available:
          status = S_TIRE_LIM_ACC
          F_tire_long = F_tire_long_available
        if eng_rpm > vehicle.engine_rpms[-1] and gear >= len(vehicle.gears)-1:
          status = S_TOPPED_OUT
    
      F_longitudinal = F_tire_long - vehicle.drag(v, aero_mode)
      a_long = F_longitudinal / vehicle.mass
      vi = v
      v = floor_sqrt(v**2 + 2*a_long*dl)
      if v > vmax:
        v = vmax
        a_long = (v**2-vi**2)/2/dl
        F_tire_long = vehicle.mass*a_long + vehicle.drag(v, aero_mode)
        topped = True
      t += 1000 if v==0 else dl/v
      x += dl



      channels[i,O_TIME]      = t
      channels[i,O_DISTANCE]  = x
      channels[i,O_VELOCITY]  = v
      channels[i,O_NR]        = N
      channels[i,O_SECTORS]   = sector.i
      channels[i,O_STATUS]    = status
      channels[i,O_GEAR]      = np.nan if status == S_SHIFTING else gear
      channels[i,O_LONG_ACC]  = a_long/vehicle.g
      channels[i,O_LAT_ACC]   = a_lat/vehicle.g
      channels[i,O_FR_REMAINING] = frem_filter(F_tire_long_available-abs(F_tire_long))
      channels[i,O_CURVATURE] = sector.curvature
      channels[i,O_ENG_RPM]   = np.nan if status == S_SHIFTING else eng_rpm
      channels[i,O_CO2]       = dl*F_tire_long*vehicle.co2_factor/vehicle.e_factor
      channels[i,O_AERO_MODE] = aero_mode
      if topped and i<n-2:
        channels[i,O_STATUS] = S_SUSTAINING
        channels[i:,:] = np.tile(channels[i,:], (n-i,1))
        for j in range(i+1,n):
          channels[j,O_TIME] += dl*(j-i)/v
          channels[j,O_DISTANCE] += dl*(j-i)
        break


    # perform reverse integration to the beginning or vmax

    if vmax-vf > 1e-1 and v>vf:
      # print('doing braking... %f -> %f' % (v,vf))
      t_peak = t
      v = vf
      t = 0
      x = x0+dl*n
      for i in reversed(range(n-1)):
        # print(x,v)
        a_lat = v**2 * derate_curvature(sector.curvature, vehicle.r_add)
        F_tire_lat = vehicle.mass * a_lat

        F_tire_long_available_FULL = vehicle.f_long_remain(4, vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_FULL), F_tire_lat)[0]
        F_tire_long_available_BRK = vehicle.f_long_remain(4, vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_BRK), F_tire_lat)[0]
        F_longitudinal_FULL = - F_tire_long_available_FULL - vehicle.drag(v, AERO_FULL)
        F_longitudinal_BRK = - F_tire_long_available_FULL - vehicle.drag(v, AERO_BRK)

        F_tire_long_available = F_tire_long_available_FULL
        F_longitudinal = F_longitudinal_FULL
        aero_mode = AERO_FULL
        N = vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_FULL)
        if F_longitudinal_FULL > F_longitudinal_BRK:
          # print('AIRBRAKE!')
          aero_mode = AERO_BRK
          F_tire_long_available = F_tire_long_available_BRK
          F_longitudinal = F_longitudinal_BRK
          N = vehicle.mass*vehicle.g + vehicle.downforce(v, AERO_BRK)

        status = S_BRAKING
      
        a_long = F_longitudinal / vehicle.mass
        v = floor_sqrt(v**2 - 2*a_long*dl)

        # print(t,x,v,a_long/vehicle.g,a_lat/vehicle.g,F_tire_engine_limit,F_tire_long_available, F_tire_lat, N)

        if v > channels[i,O_VELOCITY]:
          channels[-1,:] = channels[-2,:]
          channels[-1,O_TIME]     = -1e-10
          channels[-1,O_DISTANCE] = x0 + dl*n
          channels[-1,O_VELOCITY] = vf
          for j in reversed(range(n)):
            if channels[j,O_TIME] < 0:
              channels[j,O_TIME] += channels[i,O_TIME] - t
          break

        t -= 1000 if v==0 else dl/v
        x -= dl

        # print(t,x,v,a_long,a_lat,F_tire_engine_limit,F_tire_long_available, F_tire_lat, N)

        channels[i,O_TIME]     = t
        channels[i,O_DISTANCE] = x
        channels[i,O_VELOCITY] = v
        channels[i,O_NR]       = N
        channels[i,O_SECTORS]  = sector.i
        channels[i,O_STATUS]   = status
        channels[i,O_GEAR]     = gear
        channels[i,O_LONG_ACC] = a_long/vehicle.g
        channels[i,O_LAT_ACC]  = a_lat/vehicle.g
        channels[i,O_FR_REMAINING] = 0
        channels[i,O_CURVATURE]    = sector.curvature
        channels[i,O_ENG_RPM]      = np.nan
        channels[i,O_CO2]          = 0
        channels[i,O_AERO_MODE]    = aero_mode
      else:
        channels[-1,:] = channels[-2,:]
        channels[-1,O_TIME]     = -1e-10
        channels[-1,O_DISTANCE] = x0 + dl*n
        channels[-1,O_VELOCITY] = vf
        for j in range(n):
          if channels[j,O_TIME] < 0:
            channels[j,O_TIME] += t0 - t
    
    if abs(channels[-1,O_VELOCITY] - min(vf,vmax)) < 1:
      channels[-1,O_VELOCITY] = min(vf,vmax)

    # find intersection point and splice

    # print('Straight from %.2f -> %.2f (%.2f real, %.2f limit) (%.4f s)' % (v0,vf,channels[-1,O_VELOCITY],vmax,channels[-1,O_TIME]-channels[0,O_TIME]))

    return channels, (v0-channels[0,O_VELOCITY] >= 1e-1) and (v0 != 0)
    
  def steady_corner(self, vehicle, sector):
    # solve a fuckton of physics
    v_lower = 0
    v_upper = vehicle.vmax
    v_cur   = (v_lower + v_upper)/2.0
    v_working = 1.0
    i = 0

    N = 0
    a_lat = 0
    F_tire_long = 0
    F_tire_lat  = 0
    F_tire_lat_available = 0
    F_tire_lat_excess    = 0

    while True:
      
      N = vehicle.mass*vehicle.g + vehicle.downforce(v_cur, AERO_FULL)
      F_tire_long = vehicle.drag(v_cur, AERO_FULL)
      a_lat = v_cur**2 * derate_curvature(sector.curvature, vehicle.r_add)
      F_tire_lat  = vehicle.mass * a_lat
      F_tire_lat_available = vehicle.f_lat_remain(4, N, F_tire_long)
      F_tire_lat_excess = F_tire_lat_available[0] - F_tire_lat

      # print('iter %d; k= %.4f, v= %.2f, avail= %.3f, req= %.3f, excess= %.4f' % (i,sector.curvature,v_cur,F_tire_lat_available[0],F_tire_lat,F_tire_lat_excess))

      if F_tire_lat_excess < 2e-1 and F_tire_lat_excess >= 1e-1:
        break

      if F_tire_lat_excess > 1e-3:
        v_working = v_cur
        v_lower   = v_cur
      else:
        v_upper   = v_cur
      v_cur   = (v_lower + v_upper)/2.0

      i+=1
      if i > 100:
        v_cur = v_working
        break
    
    channels = [
      1000 if v_cur == 0 else sector.length/v_cur, # t
      sector.length, # x
      v_cur,
      0,
      0,
      N,
      0, 
      sector.i,
      S_SUSTAINING,
      np.nan, # no real 'gear'
      0, # no long. acc
      a_lat/vehicle.g, 
      0,
      0,
      0,
      0,
      F_tire_lat_available[0]-F_tire_lat,
      0,
      sector.curvature,
      np.nan, # engine could be made but enh
      sector.length*F_tire_long*vehicle.co2_factor/vehicle.e_factor,
      AERO_FULL]

    # print(sector,channels)

    channels = np.array(channels)

    return channels

  def solve(self, vehicle, sectors, output_0 = None, dl=0.2, closed_loop=False):
    # print('Sectors: %s' % repr(sectors))
    # print('Total Length: %f' % sum([x.length for x in sectors]))

    # solve all the corners
    steady_conditions = [None for i in sectors]
    steady_velocities = [vehicle.vmax for i in sectors]
    for i, sector in enumerate(sectors):
      if sector.curvature > 0:
        steady_conditions[i] = self.steady_corner(vehicle, sector)
        steady_velocities[i] = steady_conditions[i][O_VELOCITY]
    # print('Steady velocities: %s' % repr(steady_velocities))


    channel_stack = None
    starts = []

    if closed_loop:
      vf = vehicle.vmax
      if i+1<len(steady_velocities):
        vf = steady_velocities[i+1]
      elif closed_loop:
        vf = steady_velocities[-1]

      # self, vehicle, sector, x0, t0, v0, vf, vmax, gear=None, dl=0.1, start=False
      channels_corner, failed_start = self.drive(vehicle,
        sectors[0],
        0,
        0,
        min(steady_velocities[-1],steady_velocities[0]*0.95),
        vf,
        steady_velocities[0], 
        np.nan, dl, start=False)

      starts.append(0)
      channel_stack = channels_corner
    else:
      channels_corner, failed_start = self.drive(vehicle,
        sectors[0],
        0,
        0,
        0,
        vehicle.vmax if 1>=len(steady_velocities) else steady_velocities[1],
        steady_velocities[0],
        np.nan, dl, start=True)

      starts.append(0)
      channel_stack = channels_corner

    i = 1
    while i<len(sectors):
      # print(sectors[i])
      vf = vehicle.vmax
      if i+1>=len(steady_velocities):
        if closed_loop:
          vf = channel_stack[0,O_VELOCITY]
      else:
        vf = steady_velocities[i+1]

      channels_corner, failed_start = self.drive(vehicle,
        sectors[i],
        channel_stack[-1,O_DISTANCE],
        channel_stack[-1,O_TIME],
        channel_stack[-1,O_VELOCITY],
        vf,
        steady_velocities[i],
        channel_stack[-1,O_GEAR], dl)

      starts.append(channel_stack.shape[0])
      channel_stack = np.vstack((channel_stack,channels_corner))

      j = i-1
      ### DIDNT SUCCEED IN BRAKING ###
      while failed_start:
        ### KEEP WORKING BACKWARDS... ###
        # print('working backwards... (sec %d)' % j)
        k = j
        vstart = channels_corner[0,O_VELOCITY]
        if steady_velocities[k] < vstart:
          vstart = steady_velocities[k]
        
        channels_corner, success = self.brake(vehicle,
          sectors[j],
          channel_stack[starts[j],O_TIME],
          channels_corner[0,O_DISTANCE],
          vstart,
          channels_corner[0,O_VELOCITY],
          dl)
        failed_start = not success

        dt = (channels_corner[-1,O_TIME] - channels_corner[0,O_TIME]) - (channel_stack[starts[j+1],O_TIME]-channel_stack[starts[j],O_TIME])

        failed_start = not success
        after = channel_stack[starts[j+1]:,:]
        after[:,O_TIME] += dt

        channel_stack = np.vstack((channel_stack[:starts[j],:], channels_corner))
        channel_stack = np.vstack((channel_stack, after))

        di = (channels_corner.shape[0]) - (starts[j+1]-starts[j])
        k = j+1
        while k < len(starts):
          starts[k] += di
          k+=1
        
        j-=1

      i+=1

    channel_stack[:,O_CO2] = np.cumsum(channel_stack[:,O_CO2])

    return channel_stack

  def steady_solve(self, vehicle, segments, dl=0.2):
    return self.solve(vehicle, segments, dl=dl, closed_loop=True)