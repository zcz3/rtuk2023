#!/usr/bin/env python3

import sys
import glob
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from operator import itemgetter
import csv


def oh(msg):
  raise Exception(msg)

def parse_utc_time_string(ts):
  d = datetime.strptime(ts, '%Y-%m-%d %H:%M')
  return d.replace(tzinfo=timezone.utc)


MODE_LEG_MARKER = 'Stop'
MODES_STATIC = ('MoorPontoon', 'MoorBuoy', 'Anchor')
MODES_MOVING = ('Engine', 'Sail', 'MotorSail')
MODES = (MODE_LEG_MARKER, ) + MODES_STATIC + MODES_MOVING


def read_tracklog(csv_path):
  tracklog= []
  last_date = None
  current_leg = None

  with open(csv_path, 'r') as f:
    reader = csv.reader(f, delimiter=',')
    for row in reader:
      date, mode, dest = row
      date = date.strip()
      mode = mode.strip()
      dest = dest.strip()

      if len(date) + len(mode) + len(dest) == 0:
        continue

      if mode not in MODES:
        oh('Invalid mode')
      
      datep = None
      
      if mode != MODE_LEG_MARKER:
        datep = parse_utc_time_string(date)

        if last_date is not None and datep <= last_date:
          oh('Date not sequential')
        
        last_date = datep

        if len(dest):
          oh('Unexpected dest')
      
      if mode == MODE_LEG_MARKER:
        if len(dest) == 0:
          oh('No dest')
      
      if mode == MODE_LEG_MARKER and current_leg:
        current_leg['stop'] = dest
        tracklog.append(current_leg)
        current_leg = None

      if mode == MODE_LEG_MARKER and not current_leg:
        current_leg = {
          'start': dest,
          'stop': '',
          'tracks': [],
        }

      if mode != MODE_LEG_MARKER:
        if not current_leg:
          oh('Missing leg marker')
 
        current_leg['tracks'].append({
          'date': datep,
          'mode': mode,
          'dest': dest,
        })
  
  if len(current_leg['tracks']):
    oh('Missing final leg marker')

  return tracklog


GPX_NS = 'http://www.topografix.com/GPX/1/1'
NSP = '{%s}' % GPX_NS
ET.register_namespace('', GPX_NS)

class GPXWriter:

  def __init__(self):
    self.root = ET.Element(NSP + 'gpx')
    self.root.attrib['version'] = '1.1'
    self.root.attrib['creator'] = 'https://github.com/zcz3/rtuk2023'

    self.cur_trk = None
    self.cur_trkseg = None
    self.trkseg_n = 0
    self.trkpt_n = 0
  
  def start_trk(self, name):
    if self.cur_trk is not None:
      oh("trk not stopped")

    self.cur_trk = trk = ET.SubElement(self.root, NSP + 'trk')
    trk_name = ET.SubElement(self.cur_trk, NSP + 'name')
    trk_name.text = name
  
  def stop_trk(self):
    if self.cur_trk is None:
      oh("trk not started")

    if self.cur_trkseg is not None:
      oh("trkseg not stopped")
    
    if self.trkseg_n == 0:
      oh("no trksegs")

    self.cur_trk = None
    self.trkseg_n = 0
  
  def start_trkseg(self):
    if self.cur_trk is None:
      oh("trk not started")

    if self.cur_trkseg is not None:
      oh("trkseg not stopped")
    
    self.cur_trkseg = ET.SubElement(self.cur_trk, NSP + 'trkseg')
  
  def stop_trkseg(self):
    if self.cur_trk is None:
      oh("trk not started")
    
    if self.cur_trkseg is None:
      oh("trkseg not started")
    
    if self.trkpt_n == 0:
      oh("no trkpts")
    
    self.cur_trkseg = None
    self.trkpt_n = 0

    self.trkseg_n += 1
  
  # All parameters must be strings
  def add_trkpt(self, time, lat, lon, ele):
    if self.cur_trkseg is None:
      oh("trkseg not started")
    
    trkpt = ET.SubElement(self.cur_trkseg, NSP + 'trkpt')
    trkpt.attrib['lat'] = lat
    trkpt.attrib['lon'] = lon
    trk_time = ET.SubElement(trkpt, NSP + 'time')
    trk_time.text = time
    trk_ele = ET.SubElement(trkpt, NSP + 'ele')
    trk_ele.text = ele

    self.trkpt_n += 1

  def write_to_file(self, path):
    tree = ET.ElementTree(self.root)
    ET.indent(tree)

    tree.write(
      path,
      encoding='unicode',
      xml_declaration=True)



class GPXFile:

  def __init__(self):
    self._reset()

  def _reset(self):
    self.ok = False
    self.error = ''

    self.creator = 'Unknown'
    self.n_wpt = 0
    self.n_rte = 0
    self.n_trk = 0
    self.n_trkpts = 0

    self.trkpts = [] # list of dicts
    self.oldest_trkpt = None
    self.newest_trkpt = None

  def load(self, path):
    self._reset()

    try:
      et = ET.parse(path)
    except FileNotFoundError:
      self.error = 'File not found'
      return False
    except ET.ParseError:
      self.error = 'XML parse error'
      return False
    
    self.ok = self._load_et(et)
    return self.ok

  def _load_et(self, et):
    # gpx -> wpt/rte/trk
    # gpx -> trk -> trkseg -> trkpt

    root = et.getroot()
    rootname = root.tag
    if len(rootname) < 3 or rootname[-3:] != 'gpx':
      self.error = 'Not a GPX file'
      return False

    if not 'version' in root.attrib.keys() or root.attrib['version'] != '1.1':
      self.error = 'Invalid GPX version'
      return False

    if 'creator' in root.attrib.keys():
      c = root.attrib['creator'].strip()
      if len(c):
        self.creator = c

    self.n_wpt = len( et.findall('./{*}wpt'))
    self.n_rte = len( et.findall('./{*}rte'))

    trks = et.findall('./{*}trk')
    self.n_trk = len(trks)
    
    for trk in trks:
      for pt in trk.findall('.//{*}trkpt'):
        point = self._load_trkpt(pt)

        if point is False:
          self.error = 'Could not parse trkpt'
          return False
    
    return True

  def _load_trkpt(self, pt):
    # We keep these as text to preserve accuracy
    time = ''
    lat = ''
    lon = ''
    ele = ''

    try:
      lat = pt.attrib['lat']
      lon = pt.attrib['lon']
    except KeyError:
      return False
    
    timetag = pt.find('./{*}time')
    if timetag is None or timetag.text is None:
      return False

    time = timetag.text

    eletag = pt.find('./{*}ele')
    if eletag is None or eletag.text is None:
      return False

    ele = eletag.text

    if len(time) == 0 or len(lat) == 0 or len(lon) == 0 or len(ele) == 0:
      return False
    
    ptime = datetime.fromisoformat(time)
    
    self.trkpts.append({
      'time': time,
      'ptime': ptime,
      'lat': lat,
      'lon': lon,
      'ele': ele,
    })

    self.n_trkpts += 1

    if self.oldest_trkpt is None or ptime < self.oldest_trkpt:
      self.oldest_trkpt = ptime
    
    if self.newest_trkpt is None or ptime > self.newest_trkpt:
      self.newest_trkpt = ptime


def expand_globs(glob_list):
  files = []
  for g in glob_list:
    files += glob.glob(g)

  return files

def combine_trkpts(files):
  pts = {} # dict of trkpts indexed by time

  for f in files:
    gf = GPXFile()
    gf.load(f)

    if not gf.ok:
      return (False, 'Load error (%s): %s' % (f, gf.error))
    
    for p in gf.trkpts:
      if p['time'] not in pts.keys():
        pts[p['time']] = p

  return (True, sorted(list(pts.values()), key=itemgetter('time')))


def usage(exec_name):
  print("""Usage:

Print info about GPS files:
  {0} i raw_garmin73/*.gpx

Combine all tracks from multiple raw GPX files into single track in single GPX file:
  {0} cs combined.gpx raw_garmin73/*.gpx

Combine all tracks and split into legs according to CSV into single GPX file":
  {0} cf combined.gpx tracklog.csv raw_garmin73/*.gpx
""".format(exec_name), file=sys.stderr)
  sys.exit(-1)


def main(argv):
  ex = argv[0]

  if len(argv) == 1:
    usage(ex)
  
  cmd = argv[1]
  args = argv[2:]
  nargs = len(args)

  ok = False

  if cmd == 'i':
    if nargs == 0:
      usage(ex)
    
    ok = True
    
    for f in expand_globs(args):
      print('%s:' % f)
      gf = GPXFile()
      gf.load(f)

      if not gf.ok:
        print('  Load error: ' + gf.error)
      else:
        print('  Creator: ' + gf.creator)
        print('  Num wpt: %i' % gf.n_wpt)
        print('  Num rte: %i' % gf.n_rte)
        print('  Num trk: %i' % gf.n_trk)
        print('    Num trkpts: %i' % gf.n_trkpts)
        print('    Oldest trkpt: ' + gf.oldest_trkpt.isoformat())
        print('    Newest trkpt: ' + gf.newest_trkpt.isoformat())
        print('\n')

  elif cmd == 'cs':
    if nargs < 2:
      usage(ex)
    
    outpath = args[0]
    inpaths = expand_globs(args[1:])

    print('Num input files: %d' % len(inpaths))
    
    ok, res = combine_trkpts(inpaths)
    if not ok:
      print(res)
    else:
      pts = res
      print('Num unique trkpts: %d' % len(pts))
    
    of = GPXWriter()
    of.start_trk('Combined')
    of.start_trkseg()

    for p in pts:
      of.add_trkpt(p['time'], p['lat'], p['lon'], p['ele'])
    
    of.stop_trkseg()
    of.stop_trk()

    of.write_to_file(outpath)

  elif cmd == 'cf':
    if nargs < 1:
      usage(ex)
    
    outpath = COMBINED_TRACKS_FILE
    inpaths = expand_globs(args)
    filter = LEG_FILTER

    print('Num input files: %d' % len(inpaths))
    
    ok, res = combine_trkpts(inpaths)
    if not ok:
      print(res)
    else:
      pts = res
      print('Num unique trkpts: %d' % len(pts))
    
      ok, res = filter_points(pts, filter)
      if not ok:
        print(res)
      else:
        trks = res
        if not write_trks(trks, outpath):
          ok = False
          print('Could not write output')
        else:
          print('Written to ' + outpath)

  else:
    usage(ex)
  
  if not ok:
    print("Abortin'", file=sys.stderr)
    return -1

  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))
