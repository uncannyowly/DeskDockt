import unittest
from unittest.mock import Mock
from placement import geometry,validate
from native_engine import Engine
from layout_model import Model

class PlacementTests(unittest.TestCase):
    def test_one_third_at_top_corner_and_phone_mapping(self):
        zone=(1920,1200,0,0);layout=dict(monitor=list(zone),offset=-.4,size=.6)
        _,line,start,span=geometry([zone],'right',layout)
        self.assertEqual(line,(1920,0,1920,239))
        phone=Mock(width=1000,height=2400);backend=Mock();backend.monitors.return_value=[zone]
        engine=Engine(phone,backend,layout=layout)
        engine.position(1919,300);backend.capture.assert_not_called()
        engine.position(1919,0);backend.capture.assert_called_once()
        self.assertAlmostEqual(engine.y,1600) # lower third of phone, not its top
        engine.motion(-10,0)
        self.assertEqual(backend.release.call_args.args[0],(1917,0))

    def test_all_edges_negative_monitor_coordinates(self):
        z=(1000,600,-1000,-600)
        for edge,expected in [('left',(-1000,-450,-1000,-151)),('right',(0,-450,0,-151)),
                              ('top',(-750,-600,-251,-600)),('bottom',(-750,0,-251,0))]:
            self.assertEqual(geometry([z],edge,dict(monitor=list(z),offset=.25,size=.5))[1],expected)

    def test_stale_monitor_requires_repositioning(self):
        with self.assertRaisesRegex(ValueError,'Monitor layout changed'):
            geometry([(1000,600,0,0)],'right',dict(monitor=[1200,600,0,0],offset=.1,size=.5))

    def test_drag_around_monitor_and_persist_corner_overlap(self):
        callback=Mock();model=Model([(1920,1080,0,0)],dict(edge='right',phone_layout=None),callback)
        monitor,phone=model.scene(500,300);px,py,pw,ph=phone;mx,my,mw,mh=monitor
        self.assertTrue(model.begin(px+pw/2,py+ph/2,500,300))
        model.move(mx+mw*.3,my-10,500,300)
        self.assertTrue(model.enabled);edge,layout=callback.call_args.args
        self.assertEqual(edge,'top');self.assertIsNotNone(validate(layout))

    def test_invalid_or_non_overlapping_layouts(self):
        for offset,size in ((float('nan'),.5),(2,.5),(-1,.5),(0,float('inf'))):
            self.assertIsNone(validate(dict(monitor=[1920,1080,0,0],offset=offset,size=size)))

    def test_capture_cached_clipboard_precedes_input_and_opt_out_clears_it(self):
        phone=Mock(width=1000,height=2400);backend=Mock();backend.monitors.return_value=[(1920,1080,0,0)]
        engine=Engine(phone,backend);engine.clipboard.configure(True);engine.clipboard.update('ready')
        engine.position(1919,400);engine.key(50,0,True)
        self.assertEqual(phone.method_calls[0].args,('ready',))
        self.assertEqual(phone.method_calls[0][0],'clipboard')
        engine.release();engine.clipboard.configure(False);phone.reset_mock()
        engine.position(1919,400);phone.clipboard.assert_not_called()
