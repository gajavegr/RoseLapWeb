import numpy as np
import math
from sympy.solvers import solve
import sympy

from constants import *
class sim_pointmass:
  def __init__(self):
    pass

  def step(self, vehicle, prior_result, segment, segment_next, brake, shifting, gear):
    if brake:
      out_brk = self.substep(vehicle, prior_result, segment, segment_next, brake, shifting, gear, AERO_BRK)
      out_nor = self.substep(vehicle, prior_result, segment, segment_next, brake, shifting, gear, AERO_FULL)
      if out_nor is not None:
        if out_brk is not None:
          if out_brk[O_VELOCITY] < out_nor[O_VELOCITY]:
            return out_brk
          else:
            return out_nor
        else:
          return out_nor
      elif out_brk is not None:
        return out_brk
      else:
        return None
    else:
      out_drs = self.substep(vehicle, prior_result, segment, segment_next, brake, shifting, gear, AERO_DRS)
      out_nor = self.substep(vehicle, prior_result, segment, segment_next, brake, shifting, gear, AERO_FULL)
      if out_nor is not None:
        if out_drs is not None:
          if out_drs[O_VELOCITY] > out_nor[O_VELOCITY]:
            return out_drs
          else:
            return out_nor
        else:
          return out_nor
      elif out_drs is not None:
        return out_drs
      else:
        return None
    
  def substep(self, vehicle, prior_result, segment, segment_next, brake, shifting, gear, aero_mode):
    """
    Takes a vehicle step. Returns (see last line) if successful, returns None if vehicle skids off into a wall.
    @param v0 the initial vehicle speed for this step
    @param segment the Segment of the track the vehicle is on
    @param brake a boolean value specifying whether or not to apply the brakes (with full available force)
    @param shifting a shifting status code
    """

    # init values
    v0 = prior_result[O_VELOCITY];
    x0 = prior_result[O_DISTANCE];
    t0 = prior_result[O_TIME];
    status = S_TOPPED_OUT;
    co2_elapsed = prior_result[O_CO2];

    

    Ftire_lat = segment.curvature*vehicle.mass*v0**2

    Ftire_remaining, Ftire_max_long = vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.downforce(v0,aero_mode), Ftire_lat)
    if Ftire_remaining < 0:
      return None

    # if not brake:
    #   aero_mode = AERO_DRS
    #   Ftire_remaining, Ftire_max_long = vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.downforce(v0,aero_mode), Ftire_lat)
    #   if Ftire_remaining < 0:
    #     aero_mode = AERO_FULL
    #     Ftire_remaining, Ftire_max_long = vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.downforce(v0,aero_mode), Ftire_lat)
    #     if Ftire_remaining < 0:
    #       return None
    # else:
    #   aero_mode = AERO_BRK
    #   Ftire_remaining, Ftire_max_long = vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.downforce(v0,aero_mode), Ftire_lat)
    #   if Ftire_remaining < 0:
    #     aero_mode = AERO_FULL
    #     Ftire_remaining, Ftire_max_long = vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.downforce(v0,aero_mode), Ftire_lat)
    #     if Ftire_remaining < 0:
    #       return None


    Ftire_engine_limit, eng_rpm = vehicle.eng_force(v0, int(gear))
    

    

    if brake:
      status = S_BRAKING
      Ftire_long = -Ftire_remaining
      gear = np.nan
    elif shifting:
      status = S_SHIFTING
      Ftire_long = 0
      gear = np.nan
    else:
      if segment.curvature > 0 and (prior_result[O_STATUS] == S_BRAKING  or (abs(prior_result[O_CURVATURE] - segment.curvature)<=0.03 and prior_result[O_STATUS] == S_SUSTAINING)):
        status = S_SUSTAINING
        Ftire_long = vehicle.drag(v0, aero_mode)
      else:
        status = S_ENG_LIM_ACC
        Ftire_long = Ftire_engine_limit
      if Ftire_long > Ftire_remaining:
        status = S_TIRE_LIM_ACC
        Ftire_long = Ftire_remaining

    F_longitudinal = Ftire_long - vehicle.drag(v0, aero_mode)
    a_long = F_longitudinal / vehicle.mass

    try:
      vf = math.sqrt(v0**2 + 2*a_long*segment.length)
    except:
      a_long=0
      vf=0

    if status!=S_SUSTAINING and abs(F_longitudinal) < 1e-3 and shifting != IN_PROGRESS:
      status = S_DRAG_LIM

    if eng_rpm > vehicle.engine_rpms[-1]:
      status = S_TOPPED_OUT

    # Bisection to generate sustaining
    if self.compute_excess(vehicle,segment,vf,aero_mode) < 0:
      vfu = vf*2
      vfb = 0
      vfc = vf
      excess = self.compute_excess(vehicle, segment, vfc, aero_mode)
      # print(excess)

      while excess<0 or excess>1e-2:
        if (excess<0):
          vfu = vfc
        else:
          vfb = vfc
        vfc = (vfu+vfb)/2
        excess = self.compute_excess(vehicle, segment, vfc, aero_mode)
      vf = vfc
      status = S_SUSTAINING

      # vs = sympy.Symbol('vs');
      # n_tires = 4
      # print('thinking')
      # eq = -vehicle.alpha_drag()**2*vs**4 + (1-(vehicle.alpha_drag()*vs**2/n_tires)**2/(vehicle.tire_mu_x*((vehicle.mass*vehicle.g+vehicle.alpha_downforce()*vs**2)/n_tires) + vehicle.tire_offset_x)**2)**2*vehicle.tire_mu_y**2*((vehicle.mass*vehicle.g+vehicle.alpha_downforce()*vs**2)/n_tires)**2 + vehicle.tire_offset_y**2
      # print(eq)
      # vf = solve(eq, vs, numerical=True)
      # print(vf)

    vavg = ((v0+vf)/2)
    if vavg > 0:
      tf = t0 + segment.length/vavg
    else:
      tf = t0
    xf = x0 + segment.length

    if not (brake or shifting):
      co2_elapsed += segment.length*F_longitudinal*vehicle.co2_factor/vehicle.e_factor

    output = np.array([
      tf,
      xf,
      vf,
      vehicle.mass*vehicle.g + vehicle.downforce(v0,aero_mode),
      0,
      segment.sector,
      status,
      gear,
      a_long / vehicle.g, 
      (vavg ** 2) * segment.curvature / vehicle.g, 
      Ftire_remaining,
      0,
      segment.curvature,
      eng_rpm,
      co2_elapsed,
      aero_mode
    ])

    return output

  def compute_excess(self, vehicle, segment, vf, aero_mode):
    return vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.downforce(vf, aero_mode), vehicle.mass*vf**2*segment.curvature)[0] - vehicle.drag(vf, aero_mode)
    #return vehicle.f_long_remain(4, vehicle.mass*vehicle.g+vehicle.alpha_downforce()*vf**2, vehicle.mass*vf**2*segment.curvature)[0] - vehicle.alpha_drag()*vf**2;

  def solve(self, vehicle, segments, output_0 = None):
    # set up initial stuctures
    output = np.zeros((len(segments), O_MATRIX_COLS))
    precrash_output = np.zeros((len(segments), O_MATRIX_COLS))
    shifting = NOT_SHIFTING
    
    if output_0 is None:
      output[0,O_NF] = vehicle.mass*vehicle.g
      gear = vehicle.best_gear(output[0,O_VELOCITY], np.inf)
    else:
      output[0,:] = output_0
      output[0,O_TIME] = 0
      output[0,O_DISTANCE] = 0
      gear = vehicle.best_gear(output_0[O_VELOCITY], output_0[O_FR_REMAINING])

    brake = False
    shiftpt = -1
    shift_v_req = 0
    
    step_result = self.step(vehicle, output[0], segments[0], segments[1], brake, shiftpt>=0, gear)

    output[0] = step_result

    # step loop set up
    i = 1
    backup_amount = int(7.0/segments[0].length)
    bounds_found = False
    failpt = -1
    middle_brake_bound = -1
    lower_brake_bound = -1
    upper_brake_bound = -1

    while i<len(segments):
      if i<0:
        print('damnit bobby')
        return None
      if (gear is None) and shiftpt < 0:
        gear = vehicle.best_gear(output[i-1,O_VELOCITY], output[i,O_FF_REMAINING])

      step_result = self.step(vehicle,output[i-1,:], segments[i], (segments[i+1] if i+1<len(segments) else segments[i]), brake, shiftpt>=0, gear)
      if step_result is None:
        #print('crash at',i)
        if not brake:
          # Start braking

          #print('crash algo start at', i)
          precrash_output = np.copy(output)
          brake = True
          bounds_found = False
          failpt = i
          lower_brake_bound = i
          i = lower_brake_bound
          #plot_velocity_and_events(output)
          #plt.show()
        elif bounds_found:
          upper_brake_bound = middle_brake_bound

          middle_brake_bound = int((upper_brake_bound + lower_brake_bound) / 2)
          #print('bisect down', lower_brake_bound, middle_brake_bound, upper_brake_bound)
          
          i = middle_brake_bound
          output = np.copy(precrash_output)
        else:
          # Try again from an earlier point
          
          lower_brake_bound-=backup_amount
          #print('push further', lower_brake_bound)

          i = lower_brake_bound
          output = np.copy(precrash_output)
        # reset shifting params
        gear = None
        shiftpt = -1
      elif i<=failpt:
        output[i] = step_result
        i+=1
        brake = True
        # reset shifting params
        gear = None
        shiftpt = -1
        shift_v_req = 0
      elif failpt>=0 and not bounds_found:
        #print('nailed it', lower_brake_bound)
        bounds_found = True

        upper_brake_bound = failpt-1 #lower_brake_bound+backup_amount

        middle_brake_bound = int((upper_brake_bound+lower_brake_bound)/2)
        
        i = middle_brake_bound
        output = np.copy(precrash_output)
      elif failpt>=0 and bounds_found and abs(lower_brake_bound - upper_brake_bound) > 1:
        lower_brake_bound = middle_brake_bound

        middle_brake_bound = int((upper_brake_bound+lower_brake_bound)/2)
        #print('bisect up', lower_brake_bound, middle_brake_bound, upper_brake_bound)
        
        i = middle_brake_bound
        output = np.copy(precrash_output)
      else:
        # normal operation

        # quit braking
        brake = False # problematic??
        failpt = -1
        lower_brake_bound = -1
        upper_brake_bound = -1
        bounds_found = False

        output[i] = step_result

        better_gear = vehicle.best_gear(output[i,O_VELOCITY], output[i,O_FF_REMAINING])

        if shiftpt < 0 and gear != better_gear and output[i,O_STATUS]==S_ENG_LIM_ACC and output[i,O_VELOCITY]>shift_v_req:
          gear += int((better_gear-gear)/abs(better_gear-gear))
          shiftpt = i
          shift_v_req = output[i,O_VELOCITY]*1.01
        elif shiftpt < 0 and output[i,O_STATUS]==S_TOPPED_OUT and gear<len(vehicle.gears)-1:
          gear += 1
          shiftpt = i
          shift_v_req = output[i,O_VELOCITY]*1.01

        if shiftpt >= 0 and output[i,O_TIME] > output[shiftpt,O_TIME]+vehicle.shift_time:
          shiftpt = -1
          i-=1
        
        i+=1

        

    #np.savetxt('dump.csv', output, delimiter=",")
    return output

  def steady_solve(self, vehicle, segments):
    output = self.solve(vehicle,segments)
    return self.solve(vehicle,segments,output[-1, :])

  def colorgen(num_colors, idx):
    color_norm  = colors.Normalize(vmin=0, vmax=num_colors-1)
    scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv') 
    def map_index_to_rgb_color(index):
      return scalar_map.to_rgba(index)
    return map_index_to_rgb_color(idx)