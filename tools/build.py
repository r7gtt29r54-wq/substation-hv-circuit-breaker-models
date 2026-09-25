"""Export and preview editable Blender models.

Usage: blender --background --python tools/build.py -- --render
Options: --asset=NAME, --output=build, --render, --width=1400
"""
import bpy,json,struct,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
def option(name,default):return next((a.split('=',1)[1] for a in args if a.startswith('--'+name+'=')),default)
OUT=Path(option('output',str(ROOT/'build'))).resolve()
for d in ['exports','renders']:(OUT/d).mkdir(parents=True,exist_ok=True)
assets=json.loads((ROOT/'assets.json').read_text())
choice=option('asset','all');width=int(option('width','1400'))
if choice!='all':
 assets=[a for a in assets if a['name']==choice]
 if not assets:raise SystemExit('Unknown asset')

def strip_png_metadata(path):
 data=path.read_bytes();out=bytearray(data[:8]);pos=8
 while pos<len(data):
  n=int.from_bytes(data[pos:pos+4],'big');kind=data[pos+4:pos+8];chunk=data[pos:pos+n+12]
  if kind in [b'IHDR',b'PLTE',b'IDAT',b'IEND',b'tRNS',b'sRGB',b'gAMA',b'cHRM']:out.extend(chunk)
  pos+=n+12
 path.write_bytes(out)

def clean_glb(path):
 data=path.read_bytes();chunks=[];pos=12
 while pos<len(data):
  n,kind=struct.unpack_from('<I4s',data,pos);body=data[pos+8:pos+8+n];pos+=n+8
  if kind==b'JSON':
   model=json.loads(body);model['asset'].pop('generator',None);model['asset'].pop('copyright',None)
   def scrub(v):
    if isinstance(v,dict):
     v.pop('extras',None)
     for value in v.values():scrub(value)
    elif isinstance(v,list):
     for value in v:scrub(value)
   scrub(model);body=json.dumps(model,separators=(',',':')).encode();body+=b' '*((-len(body))%4)
  chunks.append(struct.pack('<I4s',len(body),kind)+body)
 body=b''.join(chunks);path.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)

for asset in assets:
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/'models'/(asset['name']+'.blend')),load_ui=False,use_scripts=False)
 scenes=list(bpy.data.scenes)
 # Exchange files contain equipment geometry; each listed pose is a static snapshot.
 if asset['kind']!='drawing':
  scene=scenes[0];bpy.context.window.scene=scene
  for pose in asset['poses']:
   scene.frame_set(pose['frame']);bpy.context.view_layer.update()
   for obj in scene.objects:obj.select_set(False)
   for obj in scene.objects:
    if obj.get('export_enabled',False) and obj.type in {'MESH','CURVE','EMPTY'}:obj.select_set(True)
   path=OUT/'exports'/(asset['name']+'-'+pose['name']+'.glb')
   bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_current_frame=True,export_extras=False,export_cameras=False,export_lights=False)
   clean_glb(path)
 if '--render' in args:
  for n,scene in enumerate(scenes,1):
   if not scene.camera:continue
   bpy.context.window.scene=scene;scene.frame_set(1)
   scene.render.use_stamp=False;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
   oldx,oldy=scene.render.resolution_x,scene.render.resolution_y
   scene.render.resolution_x=width;scene.render.resolution_y=max(1,round(width*oldy/oldx));scene.render.resolution_percentage=100
   scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.use_denoising=True
   path=OUT/'renders'/(asset['name']+f'-view-{n:02}.png');scene.render.filepath=str(path)
   bpy.ops.render.render(write_still=True);strip_png_metadata(path)
 print('Built',asset['name'],flush=True)
