import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import contextlib
import io
import agent


class ScriptModel:
    """异常验收替身；正常云端实测不使用此类。"""
    def __init__(self,actions,delay=0):self.actions=list(actions);self.inputs=[];self.delay=delay
    def decide(self,messages,timeout):
        self.inputs.append(json.loads(json.dumps(messages)))
        if self.delay:time.sleep(self.delay)
        item=self.actions.pop(0) if len(self.actions)>1 else self.actions[0]
        return {'ok':True,'value':{'raw':json.dumps(item,ensure_ascii=False),'usage':{}}}

class InlineExecutor:
    def run(self,kind,args,timeout):
        assert kind=='tool'
        try:return {'ok':True,'value':agent.execute_tool(*args)}
        except agent.AgentError as exc:return {'ok':False,'error':exc.code,'message':exc.message}

def call(name,args):return {'action':'tool','name':name,'arguments':args}
QUERY=call('query_assignments',{'start':'2026-10-27','end':'2026-11-03','status':'pending'})
DETAIL=call('get_assignment_details',{'ids':[101,102]})
EXPORT=call('export_summary',{'ids':[101,102],'filename':'upcoming.txt'})
FINAL={'action':'final','assignment_ids':[101,102],
       'summary':'实验六：工具调用与Agent，2026-10-28；设计模式练习，2026-10-30。','export_filename':'upcoming.txt'}

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.state={'queried':[101,102],'detailed':[101,102],'export':None}
        self.task=agent.Task();self.fixture=agent.ROOT/'sample_assignments.json'
        self.original=self.fixture.read_bytes()
    def tearDown(self):
        self.assertEqual(self.fixture.read_bytes(),self.original);self.temp.cleanup()
    def tool(self,name,args):return agent.execute_tool(name,args,self.fixture,self.directory,self.task,self.state)
    def run_script(self,actions,gate='approve',limits=None,fault=None,model=None):
        model=model or ScriptModel(actions)
        self.model=model
        return agent.Harness(model,self.directory,gate=agent.ConfirmationGate(gate),limits=limits,
                             executor=InlineExecutor(),fault=fault).run()
    def test_query_filters_range_and_status(self):
        result=self.tool(QUERY['name'],QUERY['arguments'])
        self.assertEqual([r['id'] for r in result['items']],[101,102])
    def test_invalid_date(self):
        with self.assertRaises(agent.AgentError):self.tool('query_assignments',{'start':'2026-10-40','end':'2026-11-03','status':'pending'})
    def test_excessive_date_range(self):
        with self.assertRaises(agent.AgentError):self.tool('query_assignments',{'start':'2026-01-01','end':'2026-11-03','status':'pending'})
    def test_unknown_tool_name(self):
        with self.assertRaises(agent.AgentError):self.tool('os.system',{'command':'echo unsafe'})
    def test_extra_arguments_rejected(self):
        with self.assertRaises(agent.AgentError):self.tool('get_assignment_details',{'ids':[101],'extra':True})
    def test_boolean_not_accepted_as_id(self):
        with self.assertRaises(agent.AgentError):self.tool('get_assignment_details',{'ids':[True]})
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(agent.AgentError):self.tool('get_assignment_details',{'ids':[101,101]})
    def test_unqueried_detail_rejected(self):
        with self.assertRaises(agent.AgentError):self.tool('get_assignment_details',{'ids':[103]})
    def test_details_return_requirements(self):
        result=self.tool('get_assignment_details',{'ids':[101,102]})
        self.assertTrue(all(r['deliverables'] and r['requirements'] for r in result['items']))
    def test_parent_path_rejected(self):
        with self.assertRaises(agent.AgentError):self.tool('export_summary',{'ids':[101,102],'filename':'../secret.txt'})
    def test_export_is_idempotent(self):
        one=self.tool('export_summary',EXPORT['arguments']);two=self.tool('export_summary',EXPORT['arguments'])
        self.assertEqual((one['state'],two['state']),('created','already_exists'));self.assertEqual(one['sha256'],two['sha256'])
    def test_different_existing_file_not_overwritten(self):
        (self.directory/'upcoming.txt').write_text('原文件',encoding='utf-8')
        with self.assertRaises(agent.AgentError):self.tool('export_summary',EXPORT['arguments'])
        self.assertEqual((self.directory/'upcoming.txt').read_text(encoding='utf-8'),'原文件')
    def test_normal_simulated_loop_is_verified(self):
        result=self.run_script([QUERY,DETAIL,EXPORT,FINAL])
        self.assertEqual(result['status'],'SUCCESS');self.assertEqual(result['steps'],4)
    def test_error_feedback_is_in_next_model_context(self):
        bad=call('query_assignments',{'start':'bad','end':'2026-11-03','status':'pending'})
        result=self.run_script([bad,QUERY,DETAIL,EXPORT,FINAL])
        self.assertEqual((result['status'],result['corrections']),('SUCCESS',1))
        self.assertIn('INVALID_ARGUMENTS',self.model.inputs[1][-1]['content'])
    def test_tool_failure_has_finite_corrections(self):
        result=self.run_script([QUERY],fault={'tool':'query_assignments','kind':'raise'})
        self.assertEqual((result['status'],result['corrections']),('CORRECTION_LIMIT',3))
        self.assertIn('TOOL_EXCEPTION',self.model.inputs[1][-1]['content'])
    def test_maximum_steps_stops_without_success(self):
        result=self.run_script([QUERY],limits=agent.Limits(max_steps=2))
        self.assertEqual((result['status'],result['steps']),('STEP_LIMIT',2))
    def test_total_time_limit_prevents_tool_execution(self):
        model=ScriptModel([QUERY],delay=.03)
        result=self.run_script([],model=model,limits=agent.Limits(total_timeout=.01))
        self.assertEqual(result['status'],'TIME_LIMIT');self.assertFalse(any(e['event']=='tool_requested' for e in result['events']))
    def test_confirmation_approval_creates_file(self):
        result=self.run_script([QUERY,DETAIL,EXPORT,FINAL])
        self.assertEqual(result['status'],'SUCCESS');self.assertTrue((self.directory/'exports/upcoming.txt').exists())
        self.assertTrue(any(e['event']=='confirmation_result' and e['source']=='simulation' for e in result['events']))
    def test_confirmation_rejection_prevents_write(self):
        result=self.run_script([QUERY,DETAIL,EXPORT],gate='reject')
        self.assertEqual(result['status'],'REJECTED');self.assertFalse((self.directory/'exports/upcoming.txt').exists())
    def test_confirmation_timeout_prevents_write(self):
        result=self.run_script([QUERY,DETAIL,EXPORT],gate='timeout')
        self.assertEqual(result['status'],'CONFIRMATION_TIMEOUT');self.assertFalse((self.directory/'exports/upcoming.txt').exists())
    def test_claiming_success_does_not_pass(self):
        result=self.run_script([FINAL])
        self.assertEqual(result['status'],'CORRECTION_LIMIT');self.assertIn('缺少详情',result['events'][3]['message'])
    def test_missing_summary_fields_not_accepted(self):
        final={**FINAL,'summary':'已经全部完成。'}
        result=self.run_script([QUERY,DETAIL,EXPORT,final])
        self.assertEqual(result['status'],'CORRECTION_LIMIT')
    def test_partial_export_cannot_pass(self):
        partial=call('export_summary',{'ids':[101],'filename':'partial.txt'})
        result=self.run_script([QUERY,DETAIL,partial])
        self.assertEqual(result['status'],'CORRECTION_LIMIT');self.assertFalse((self.directory/'exports/partial.txt').exists())
    def test_export_failure_reconciles_before_stopping(self):
        self.directory.joinpath('exports').mkdir();self.directory.joinpath('exports/upcoming.txt').write_text('保持原文',encoding='utf-8')
        result=self.run_script([QUERY,DETAIL,EXPORT],fault={'tool':'export_summary','kind':'raise'})
        self.assertEqual(result['status'],'WRITE_REVIEW_REQUIRED');self.assertTrue(any(e['event']=='write_reconciliation' for e in result['events']))
        self.assertEqual(self.directory.joinpath('exports/upcoming.txt').read_text(encoding='utf-8'),'保持原文')
    def test_malformed_action_gets_bounded_error(self):
        result=self.run_script([{'action':'shell','command':'anything'}])
        self.assertEqual(result['status'],'CORRECTION_LIMIT')
    def test_logs_contain_task_id_time_and_tool_duration(self):
        result=self.run_script([QUERY,DETAIL,EXPORT,FINAL])
        events=[json.loads(s) for s in Path(result['log_file']).read_text(encoding='utf-8').splitlines()]
        self.assertTrue(all(e['task_id'] and e['time'] and 'step' in e for e in events))
        self.assertTrue(all('duration_ms' in e for e in events if e['event']=='tool_result'))
    def test_secret_redaction(self):
        output=agent.safe({'api_key':'hidden','text':'sk-'+'a'*32})
        self.assertNotIn('api_key',output);self.assertEqual(output['text'],'[REDACTED]')
    def test_process_executor_runs_real_tool(self):
        result=agent.ProcessExecutor().run('tool',('query_assignments',QUERY['arguments'],str(self.fixture),str(self.directory),self.task,self.state,None),3)
        self.assertTrue(result['ok']);self.assertEqual(len(result['value']['items']),2)
    def test_timeout_terminates_worker(self):
        result=agent.ProcessExecutor().run('tool',('query_assignments',QUERY['arguments'],str(self.fixture),str(self.directory),self.task,self.state,
            {'tool':'query_assignments','kind':'sleep','seconds':2}),.25)
        self.assertEqual(result['error'],'TOOL_TIMEOUT');self.assertTrue(result['worker_terminated'])
    @unittest.skipUnless(agent.os.name=='nt','Windows控制台计时分支')
    def test_console_confirmation_real_timeout(self):
        started=time.monotonic()
        with patch('sys.stdin.isatty',return_value=True),patch('msvcrt.kbhit',return_value=False),contextlib.redirect_stdout(io.StringIO()):
            result=agent.ConfirmationGate().request({'filename':'upcoming.txt','content':'测试预览'},.03)
        self.assertEqual(result,{'decision':'timeout','source':'console'})
        self.assertGreaterEqual(time.monotonic()-started,.03)
    @unittest.skipUnless(agent.os.name=='nt','Windows控制台确认分支')
    def test_console_approval_requires_exact_phrase(self):
        characters=iter('EXPORT upcoming.txt\r')
        with patch('sys.stdin.isatty',return_value=True),patch('msvcrt.kbhit',return_value=True),patch('msvcrt.getwch',side_effect=lambda:next(characters)),contextlib.redirect_stdout(io.StringIO()):
            result=agent.ConfirmationGate().request({'filename':'upcoming.txt','content':'测试预览'},1)
        self.assertEqual(result['decision'],'approve')
    @unittest.skipUnless(agent.os.name=='nt','Windows控制台拒绝分支')
    def test_console_wrong_phrase_rejects(self):
        characters=iter('yes\r')
        with patch('sys.stdin.isatty',return_value=True),patch('msvcrt.kbhit',return_value=True),patch('msvcrt.getwch',side_effect=lambda:next(characters)),contextlib.redirect_stdout(io.StringIO()):
            result=agent.ConfirmationGate().request({'filename':'upcoming.txt','content':'测试预览'},1)
        self.assertEqual(result['decision'],'reject')

if __name__=='__main__':unittest.main(verbosity=2)
