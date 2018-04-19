import fancyyaml
import track_segmentation
import vehicle
import sims
import StringIO

def process_input(config_filename):

	# load the config file
	with open('./params/batcher_config/' + config_filename) as data:
		conf = fancyyaml.load(data, True)

	tracks = [(track_segmentation.dxf_to_segments('./params/DXFs/' + x.dxf, x.segment_distance), x.steady_state, x.dxf) for x in conf.tracks]
	model = sims.Simulation(conf.model)
	out = (conf.filename, conf.data_percentage)

	return (conf.tests, conf.vehicle, tracks, model, out)

def process_web_config(config_text):
	# load config file
	# load vehicle into conf
	# return input pieces

	config_stream = StringIO.StringIO(config_text)
	conf = fancyyaml.load(config_stream, False)
	config_stream.close()

	return conf

def process_web_input(conf):
	vehicle_stream = StringIO.StringIO(conf.vehicle)
	conf.vehicle = vehicle.Vehicle(fancyyaml.load(vehicle_stream, False))
	vehicle_stream.close()

	tracks = [(track_segmentation.dxf_to_segments(x.dxf, x.segment_distance), x.steady_state, x.dxf) for x in conf.tracks]
	model = sims.Simulation(conf.model)
	out = (conf.filename, conf.data_percentage)

	return (conf.tests, conf.vehicle, tracks, model, out)
