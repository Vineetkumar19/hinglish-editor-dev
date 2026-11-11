from pathlib import Path
import hashlib,json
root=Path.cwd();base=root/'tools/hyperframes-runtime/node_modules/hyperframes/dist';out=root/'output/gpu-routing-20261029';entries=[]
patches=[('chunk-YCW345M4.js','  return cachedGpuEncoder;\n}', '  if (cachedGpuEncoder === null) throw new Error("GPU encoder unavailable. Keep the saved project and retry when the NVIDIA GPU is available; CPU fallback is disabled.");\n  return cachedGpuEncoder;\n}'),('render-J33ZHR6I.js','    if (encoderMode === "software" && gpuRequested && !options.quiet) {\n      console.warn(c.warn("  No GPU encoder works on this machine; encoding with libx264."));\n    }','    if (encoderMode === "software" && gpuRequested) {\n      throw new Error("GPU encoder unavailable. Keep the saved project and retry when the NVIDIA GPU is available; CPU fallback is disabled.");\n    }')]
for name,old,new in patches:
 p=base/name;s=p.read_text(encoding='utf-8');before=hashlib.sha256(p.read_bytes()).hexdigest()
 if new not in s:
  assert s.count(old)==1,name
  backup=out/(name+'.before-gpu-required');backup.write_bytes(p.read_bytes())
  p.write_text(s.replace(old,new,1),encoding='utf-8')
 entries.append({'file':str(p.relative_to(root)),'before':before,'after':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/'hyperframes-required-patch.json').write_text(json.dumps({'scope':'Pinned bundled runtime only; explicit GPU requests fail rather than switching to CPU. Existing loaded workers untouched.','files':entries},indent=2),encoding='utf-8')
