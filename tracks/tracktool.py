#!/usr/bin/env python3

import sys
import glob
import xml.etree.ElementTree as ET
from datetime import datetime
from operator import itemgetter

COMBINED_TRACKS_FILE = 'James_RTUK23_Tracks.gpx'

LEG_FILTER = (
  ('Gosport to Dover',              ('2023-04-22T15:11:49Z', '2023-04-23T10:47:49Z')),
  ('Dover to Ramsgate',             ('2023-04-25T14:59:49Z', '2023-04-25T18:44:54Z')),
  ('Ramsgate to Harwich',           ('2023-04-26T05:50:21Z', '2023-04-26T16:58:53Z')),
  ('Harwich to Woodbridge',         ('2023-04-27T13:14:04Z', '2023-04-27T17:05:39Z')),
  ('Woodbridge to Lowestoft',       ('2023-04-30T07:34:46Z', '2023-04-30T16:41:02Z')),
  ('Lowestoft to Scarborough',      ('2023-05-03T10:39:57Z', '2023-05-04T09:30:06Z')),
  ('Scarborough to Tyne',           ('2023-05-08T05:50:57Z', '2023-05-08T23:35:11Z')),
  ('Tyne to Blyth',                 ('2023-05-13T12:55:25Z', '2023-05-13T15:43:06Z')),
  ('Blyth to Newton Haven ⚓',      ('2023-05-15T09:58:32Z', '2023-05-15T19:34:58Z')),
  ('Newton Haven ⚓ to Eyemouth',   ('2023-05-16T09:19:34Z', '2023-05-16T19:09:29Z',
                                     '2023-05-16T20:18:33Z', '2023-05-16T20:47:24Z')),
  ('Eyemouth to Arbroath',          ('2023-05-18T04:08:11Z', '2023-05-18T12:12:59Z')),
  ('Arbroath to Peterhead',         ('2023-05-20T12:38:18Z', '2023-05-21T03:26:31Z')),
  ('Peterhead to Wick',             ('2023-05-25T06:44:48Z', '2023-05-26T05:30:07Z')),
)


def combine_trkpts(gpx_list):
  pts = {} # dict of trkpts indexed by time

  for f in gpx_list:
    gf = GPXFile()
    gf.load(f)

    if not gf.ok:
      return (False, 'Load error (%s): %s' % (f, gf.error))
    
    for p in gf.trkpts:
      if p['time'] not in pts.keys():
        pts[p['time']] = p

  return (True, sorted(list(pts.values()), key=itemgetter('time')))

def filter_points(pts, filter):
  # pts is list of points (each point being a dict with time, lat, lon, ele in text)
  # assumes filter legs are in time order and not overlapping
  # return val is suitable for write_trks()

  n_legs = len(filter)
  n_pts = len(pts)
  c_pt = 0

  if not n_legs or not n_pts:
    return (False, 'Empty filter or points')
  
  trks = {}

  for leg_name, leg_segs in filter:
    rngs = []
    for i in range(len(leg_segs)):
      if i & 1:
        rngs.append((
          datetime.fromisoformat(leg_segs[i-1]), datetime.fromisoformat(leg_segs[i])
        ))
    
    segs = []
    
    for start, end in rngs:
      seg_pts = []
  
      while c_pt < n_pts:
        pt = pts[c_pt]
        ptime = datetime.fromisoformat(pt['time'])

        if ptime > end:
          break

        c_pt += 1

        if ptime < start:
          continue

        seg_pts.append(pt)
      
      if len(seg_pts) == 0:
        return (False, 'Empty segment in ' + leg_name)
      
      segs.append(seg_pts)

    if len(segs) == 0:
      return (False, 'Empty leg: ' + leg_name)
    
    trks[leg_name] = segs
  
  if len(trks) == 0:
    return (False, 'No legs')
  
  return (True, trks)

def write_trks(trks, gpx_name):
  # trks is dict of track name to list of segments
  # each segment is a list of points
  # each point is a dict with time, lat, lon, ele in text

  GPX_NS = 'http://www.topografix.com/GPX/1/1'
  NSP = '{%s}' % GPX_NS
  ET.register_namespace('', GPX_NS)

  root = ET.Element(NSP + 'gpx')
  root.attrib['version'] = '1.1'
  root.attrib['creator'] = 'https://github.com/zcz3/rtuk2023'

  for tname in trks:
    tsegs = trks[tname]
    if len(tsegs) == 0:
      return False

    trk = ET.SubElement(root, NSP + 'trk')
    name = ET.SubElement(trk, NSP + 'name')
    name.text = tname

    for tseg in tsegs:
      if len(tseg) == 0:
        return False

      seg = ET.SubElement(trk, NSP + 'trkseg')

      for tpt in tseg:
        trkpt = ET.SubElement(seg, NSP + 'trkpt')
        trkpt.attrib['lat'] = tpt['lat']
        trkpt.attrib['lon'] = tpt['lon']
        time = ET.SubElement(trkpt, NSP + 'time')
        time.text = tpt['time']
        ele = ET.SubElement(trkpt, NSP + 'ele')
        ele.text = tpt['ele']
  
  tree = ET.ElementTree(root)
  ET.indent(tree)

  tree.write(
    gpx_name,
    encoding='unicode',
    xml_declaration=True)
  
  return True




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
    self.oldest_trkpt = ''
    self.newest_trkpt = ''

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
    
    self.trkpts.append({
      'time': time,
      'lat': lat,
      'lon': lon,
      'ele': ele,
    })

    self.n_trkpts += 1

    if len(self.oldest_trkpt) == 0 or time < self.oldest_trkpt:
      self.oldest_trkpt = time
    
    if len(self.newest_trkpt) == 0 or time > self.newest_trkpt:
      self.newest_trkpt = time



def usage(exec_name):
  print("""Usage:

Print info about GPS files:
  {0} i raw_garmin73/*.gpx

Combine all tracks from multiple raw GPX files into single track in single GPX file:
  {0} cs combined.gpx raw_garmin73/*.gpx

Combine all tracks and then split again according to LEG_FILTER into single GPX file called \"{1}\":
  {0} cf raw_garmin73/*.gpx

Combine all tracks and export only those that occur since LEG_FILTER into a single GPX files called \"Recent_Tracks.gpx\":
  {0} cn newtracks.gpx raw_garmin73/*.gpx
""".format(exec_name, COMBINED_TRACKS_FILE), file=sys.stderr)
  sys.exit(-1)

def expand_globs(glob_list):
  files = []
  for g in glob_list:
    files += glob.glob(g)

  return files

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
        print('    Oldest trkpt: ' + gf.oldest_trkpt)
        print('    Newest trkpt: ' + gf.newest_trkpt)
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
    
    outpts = {
      'Combined': [ pts, ]
    }

    if not write_trks(outpts, outpath):
      print('Could not write output')

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
