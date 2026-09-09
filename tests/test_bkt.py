import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BayesianKnowledgeTracingTests(unittest.TestCase):
    def _run_node(self, expression: str) -> dict:
        script = """
const BKT=require('./mindcrafted/engine/bkt.js');
const result=(%s);
process.stdout.write(JSON.stringify(result));
""" % expression
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return json.loads(completed.stdout)

    def test_correct_and_incorrect_observations_move_mastery(self):
        result = self._run_node("""function(){
          const prior=0.25;
          return {correct:BKT.update(prior,true),incorrect:BKT.update(prior,false)};
        }()""")
        self.assertGreater(result["correct"], 0.25)
        self.assertLess(result["incorrect"], 0.25)

    def test_tracker_persists_attempts_and_reaches_mastery(self):
        result = self._run_node("""function(){
          let raw=null;
          const storage={getItem:()=>raw,setItem:(_key,value)=>{raw=value;}};
          const tracker=BKT.createTracker({scope:'curso-1',storage});
          for(let i=0;i<4;i++)tracker.observe('fracciones',true,{score:90,label:'Fracciones'});
          const record=tracker.get('fracciones');
          return {record,summary:tracker.summary()};
        }()""")
        self.assertEqual(result["record"]["attempts"], 4)
        self.assertEqual(result["record"]["correct"], 4)
        self.assertTrue(result["record"]["mastered"])
        self.assertGreaterEqual(result["record"]["mastery"], 0.8)
        self.assertEqual(result["summary"]["skills"], 1)


if __name__ == "__main__":
    unittest.main()
