-- grid.lua : DLR-PAR nozzle + external plume region, 2D axisymmetric.
-- Eilmer 5 (lmr).  Built with the same idioms as
--   gdtk/examples/lmr/2D/nozzle-conical-back/grid.lua   (CoonsPatch from edge paths)
--   gdtk/examples/lmr/2D/underexpanded-jet/grid.lua     (ambient/outflow plume blocks)
--
-- Case parameters (mesh level, gas, wall config, NPR) come from case.lua.
dofile("case.lua")

config.dimensions = 2
config.axisymmetric = true

------------------------------------------------------------------------------
-- Nozzle wall: the 385 real digitized points, used as-is (metres).
------------------------------------------------------------------------------
local wall_pts = dofile("dlr_par_real_geometry.lua")
local npts = #wall_pts
assert(npts == 385, "expected 385 wall points, got " .. npts)

-- Throat = the data point of minimum radius (first occurrence).
local it = 1
for k = 2, npts do
   if wall_pts[k][2] < wall_pts[it][2] then it = k end
end

local function polyline(k0, k1)
   local segs = {}
   for k = k0, k1-1 do
      local a = wall_pts[k]; local b = wall_pts[k+1]
      segs[#segs+1] = Line:new{p0=Vector3:new{x=a[1], y=a[2]},
                               p1=Vector3:new{x=b[1], y=b[2]}}
   end
   return Polyline:new{segments=segs}
end
local wall_conv = polyline(1, it)     -- inlet -> throat
local wall_div  = polyline(it, npts)  -- throat -> exit

local x_in  = wall_pts[1][1];    local r_in  = wall_pts[1][2]
local x_t   = wall_pts[it][1];   local r_t   = wall_pts[it][2]
local x_ex  = wall_pts[npts][1]; local r_ex  = wall_pts[npts][2]
print(string.format("Nozzle: x_in=%.6f r_in=%.6f  throat(pt %d) x=%.6f r=%.6f  exit x=%.6f r=%.6f",
                    x_in, r_in, it, x_t, r_t, x_ex, r_ex))

------------------------------------------------------------------------------
-- Mesh level table (nozzle niv/njv per SPEC section 5).
-- beta: Roberts clustering toward the wall (closer to 1 => stronger).
------------------------------------------------------------------------------
local levels = {
   [0] = {niv=80,  njv=30,  beta=1.05,  niv_p=50,  njv_o=30,  niv_u=15},  -- exploration
   [1] = {niv=150, njv=60,  beta=1.01,  niv_p=85,  njv_o=50,  niv_u=25},  -- coarse
   [2] = {niv=220, njv=90,  beta=1.003, niv_p=120, njv_o=70,  niv_u=35},  -- medium
   [3] = {niv=320, njv=130, beta=1.001, niv_p=170, njv_o=100, niv_u=50},  -- fine
   -- Wall-resolution study (Nov 2026). Same streamwise grids as L2 / L3; only the
   -- wall-normal direction of the nozzle changes.
   --   22 : L2 streamwise, L3 wall-normal  -> isolates wall resolution from shock resolution
   --   33 : L3 streamwise, wall-normal much finer than L3 -> is L3 converged at the wall?
   [22] = {niv=220, njv=130, beta=1.001,  niv_p=120, njv_o=70,  niv_u=35},
   [33] = {niv=320, njv=200, beta=1.0003, niv_p=170, njv_o=100, niv_u=50},
}
local L = levels[case.mesh_level]
assert(L, "unknown mesh_level " .. tostring(case.mesh_level))

------------------------------------------------------------------------------
-- Nozzle interior, split at the throat plane into two blocks:
--   conv : inlet -> throat   (initially filled with reservoir gas)
--   div  : throat -> exit    (initially ambient gas)
-- south = axis, north = wall.  niv is shared 25% / 75%.
------------------------------------------------------------------------------
local a0 = Vector3:new{x=x_in, y=0.0}
local a1 = Vector3:new{x=x_in, y=r_in}
local t0 = Vector3:new{x=x_t,  y=0.0}
local t1 = Vector3:new{x=x_t,  y=r_t}
local e0 = Vector3:new{x=x_ex, y=0.0}
local e1 = Vector3:new{x=x_ex, y=r_ex}

local throat_line = Line:new{p0=t0, p1=t1}
local conv_patch = CoonsPatch:new{north=wall_conv, east=throat_line,
                                  south=Line:new{p0=a0, p1=t0},
                                  west=Line:new{p0=a0, p1=a1}}
local div_patch  = CoonsPatch:new{north=wall_div, east=Line:new{p0=e0, p1=e1},
                                  south=Line:new{p0=t0, p1=e0},
                                  west=throat_line}

local n_conv = math.floor(0.25*L.niv + 0.5)
local n_div  = L.niv - n_conv
local cf_r    = RobertsFunction:new{end0=false, end1=true, beta=L.beta}   -- toward wall
local cf_xc   = RobertsFunction:new{end0=false, end1=true, beta=1.2}      -- toward throat
local cf_xd   = RobertsFunction:new{end0=true, end1=false, beta=1.2}      -- toward throat
local conv_grid = StructuredGrid:new{psurface=conv_patch, niv=n_conv+1, njv=L.njv+1,
                                     cfList={west=cf_r, east=cf_r,
                                             south=cf_xc, north=cf_xc}}
local div_grid  = StructuredGrid:new{psurface=div_patch, niv=n_div+1, njv=L.njv+1,
                                     cfList={west=cf_r, east=cf_r,
                                             south=cf_xd, north=cf_xd}}

------------------------------------------------------------------------------
-- External region (Phase 1 fix 1: enlarged, and wrapped upstream of the exit
-- so entrained ambient gas arrives from upstream instead of recirculating
-- at the outflow corner).
--   core     : x_ex..x_ex+Lp,  0..r_ex   (shares nodes with nozzle exit)
--   outer    : x_ex..x_ex+Lp,  r_ex..Rp
--   upstream : x_ex-Lu..x_ex,  r_ex..Rp  (south face = engine shroud at r=r_ex,
--                                         zero-thickness nozzle lip)
------------------------------------------------------------------------------
local Lp = 0.40   -- m, ~7.3 exit radii downstream
local Rp = 0.30   -- m, ~5.5 exit radii
local Lu = 0.10   -- m, shroud length upstream of the exit plane
local p0 = Vector3:new{x=x_ex+Lp, y=0.0}
local p1 = Vector3:new{x=x_ex+Lp, y=r_ex}
local q0 = Vector3:new{x=x_ex,    y=Rp}
local q1 = Vector3:new{x=x_ex+Lp, y=Rp}
local u0 = Vector3:new{x=x_ex-Lu, y=r_ex}
local u1 = Vector3:new{x=x_ex-Lu, y=Rp}

local cf_x  = RobertsFunction:new{end0=true, end1=false, beta=1.05}  -- cluster at exit plane
local cf_ro = RobertsFunction:new{end0=true, end1=false, beta=1.05}  -- cluster at lip radius
local cf_xu = RobertsFunction:new{end0=false, end1=true, beta=1.1}   -- cluster toward lip

local core_patch  = CoonsPatch:new{p00=e0, p10=p0, p11=p1, p01=e1}
local outer_patch = CoonsPatch:new{p00=e1, p10=p1, p11=q1, p01=q0}
local up_patch    = CoonsPatch:new{p00=u0, p10=e1, p11=q0, p01=u1}
local up_grid = StructuredGrid:new{psurface=up_patch,
                                   niv=L.niv_u+1, njv=L.njv_o+1,
                                   cfList={south=cf_xu, north=cf_xu,
                                           west=cf_ro, east=cf_ro}}
local core_grid  = StructuredGrid:new{psurface=core_patch,
                                      niv=L.niv_p+1, njv=L.njv+1,
                                      cfList={south=cf_x, north=cf_x,
                                              west=cf_r, east=cf_r}}
local outer_grid = StructuredGrid:new{psurface=outer_patch,
                                      niv=L.niv_p+1, njv=L.njv_o+1,
                                      cfList={south=cf_x, north=cf_x,
                                              west=cf_ro, east=cf_ro}}

------------------------------------------------------------------------------
-- Register blocks.  Nozzle split axially for thread/MPI parallelism.
------------------------------------------------------------------------------
registerFluidGrid{grid=conv_grid, fsTag="reservoir",
                  bcTags={west="inflow", north="wall"}}
registerFluidGridArray{grid=div_grid, nib=case.nib_div or 3, njb=1,
                       fsTag="initial", bcTags={north="wall"}}
registerFluidGridArray{grid=core_grid, nib=2, njb=1, fsTag="initial",
                       bcTags={east="outflow_core"}}
registerFluidGridArray{grid=outer_grid, nib=2, njb=1, fsTag="initial",
                       bcTags={north="ambient", east="outflow_outer"}}
registerFluidGrid{grid=up_grid, fsTag="initial",
                  bcTags={south="shroud", west="ambient", north="ambient"}}
-- south edges (y=0) left untagged => default slip wall = symmetry axis.

identifyGridConnections()
