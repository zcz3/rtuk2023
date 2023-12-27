
import sys
import csv
import pprint
import datetime

from tracktool import oh, read_tracklog, expand_globs, combine_trkpts, MODES_STATIC, MODES_MOVING


# Returns (first trkpt before, closest trkpt, first trkpt after)
# trkpt must be within 5mins
def match_trkpt(time, points, thresh_mins=20):
  before = None
  after = None
  last = None

  for pt in points:
    if pt['ptime'] > time:
      after = pt
      before = last
      break
    
    last = pt
  
  thresh = datetime.timedelta(minutes=thresh_mins)
  if before and (time - before['ptime']) > thresh:
    before = None
  if after and (after['ptime'] - time) > thresh:
    after = None
  
  close = None

  if before and after:
    if (time - before['ptime']) < (after['ptime'] - time):
      close = before
    else:
      close = after
  
  return (before, close, after)





def main(argv):
  out_path = argv[1]
  tracklog_path = argv[2]
  gpx_files = expand_globs(argv[3:])

  legs = read_tracklog(tracklog_path)
  print('Num legs: %d' % len(legs))

  ok, res = combine_trkpts(gpx_files)
  if not ok:
    oh(res)

  pts = res
  print('Num unique trkpts: %d' % len(pts))

  for leg in legs:
    last_mode = None

    for t in leg['tracks']:
      (before, close, after) = match_trkpt(t['date'], pts)
      pt = None
      mode = None
      if t['mode'] in MODES_STATIC:
        mode = 'Static'
      if t['mode'] in MODES_MOVING:
        mode = 'Dynamic'
      
      if mode == 'Static':
        if last_mode == 'Dynamic':
          pt = before
          if not pt:
            oh("Could not find trkpt before "+ t['date'].isoformat())
      
      elif mode == 'Dynamic':
        if last_mode == 'Static' or last_mode is None:
          pt = after
          if not pt:
            oh("Could not find trkpt after " + t['date'].isoformat())
        
        if last_mode == 'Dynamic':
          pt = close
          if not pt:
            oh("Could not find trkpt")
      
      else:
        oh("Invalid mode")
      
      t['trkpt'] = pt

      last_mode = mode




  pprint.pprint(legs)

  return 0



if __name__ == "__main__":
  sys.exit(main(sys.argv))

