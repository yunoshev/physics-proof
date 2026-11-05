import json
ev=json.load(open("workspace/evidence.json"))
# fix scale sigma
ev["scale"]["sigma_m_per_px"]=0.0005356834331214545
# fix error budget
ev["error_budget"]["components"]=[
 {"name":"reference_size","sigma_contribution":0.053491889125479496,"basis":"quoted backpack height spread over fitted gravity"},
 {"name":"pixel_scale","sigma_contribution":0.03512900181374773,"basis":"two pixel endpoint error on the backpack extent"},
 {"name":"fit","sigma_contribution":0.029488126218625413,"basis":"parabola residuals over the free-flight window"},
 {"name":"point_vs_com","sigma_contribution":0.04936038031750245,"basis":"backpack centroid versus whole-body centroid fit difference"},
 {"name":"repetition_spread","sigma_contribution":0.037758225752962615,"basis":"spread across the two repetition fits"}
]
ev["error_budget"]["sigma_relative"]=0.07983597544141642
# fix clock natural range to 1-2 Hz slow walking source
ev["clock"]["natural_range_hz"]=[1.0,2.0]
ev["clock"]["natural_range_source"]={"url":"https://patents.justia.com/patent/9226705","quote":"However, the preferred frequency of the wave is in the range of 1 to 2 Hz to allow for variations in individuals and other factors."}
open("workspace/evidence.json","w").write(json.dumps(ev))
print("updated", ev["scale"], ev["error_budget"])
