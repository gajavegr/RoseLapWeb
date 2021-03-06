from sim_onetire import *
from sim_ss_onetire import *
from sim_twotires import *
from sim_fourtires import *
from sim_dp_nd_template import *
from sim_ss_twotires import *
from sim_ss_fourtires import *

class Simulation:
	def __init__(self, model_type="one_tire"):
		self.name = model_type
		
		if model_type == "one_tire":
			self.model = sim_onetire()
		elif model_type == "two_tires":
			self.model = sim_twotires()
		elif model_type == "four_tires":
			self.model = sim_fourtires()
		elif model_type == "ss_one_tire":
			self.model = sim_ss_onetire()
		elif model_type == "ss_two_tires":
			self.model = sim_ss_twotires()
		elif model_type == "ss_four_tires":
			self.model = sim_ss_fourtires()
		elif model_type == "dp_nd":
			self.model = sim_dp_nd_template()
		else:
			raise ValueError("Please provide a valid simulation model.")

	def copy(self):
		if self.name == "one_tire":
			return sim_onetire()
		elif self.name == "two_tires":
			return sim_twotires()
		elif self.name == "four_tires":
			return sim_fourtires()
		elif self.name == "ss_one_tire":
			return sim_ss_onetire()
		elif self.name == "ss_two_tires":
			return sim_ss_twotires()
		elif self.name == "ss_four_tires":
			return sim_ss_fourtires()
		elif self.name == "dp_nd":
			return sim_dp_nd_template()
		# else:
		# 	raise ValueError("Please provide a valid simulation model.")

	def solve(self, vehicle, segments, dl=0.3):
		if self.name[:3] == 'ss_':
			return self.model.solve(vehicle, segments, dl=dl)
		else:
			return self.model.solve(vehicle, segments)

	def steady_solve(self, vehicle, segments, dl=0.3):
		if self.name[:3] == 'ss_':
			return self.model.steady_solve(vehicle, segments, dl=dl)
		else:
			return self.model.steady_solve(vehicle, segments)