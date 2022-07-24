#! /usr/bin/env python

import argparse
import sys
import yaml
import logging
sys.path.insert(0, 'C:\DEV\GIT\execmd\\')
from execmd import execmd



g_logger = logging.getLogger("test_commands")
logging.basicConfig(level=logging.INFO)

def convert_all_yaml_cmds_into_cmds_list(yaml_cmds):
	"""
	Converts all commands described in the yaml document into a list of tuples where each tuple describes a single command, its arguments, and its expected results.
	
	Parameters:
		yaml_cmds (dict): yaml doc specifying commands to run and report on.

	Returns:
		List of dicts
	"""
	if isinstance(yaml_cmds, list):
		cmd_list = []
		for cmd in yaml_cmds:
			cmd_list.append(convert_yaml_cmds_into_cmds_list(cmd))
		return cmd_list
	elif isinstance(yaml_cmds, dict):
		return [convert_yaml_cmds_into_cmds_list(yaml_cmds)]
	else:
		raise Exception(f"yaml_cmds expected to be List of Dict's or Dict. Instead found {type(yaml_cmds)}")

def convert_yaml_cmds_into_cmds_list(yaml_cmds):
	"""
	Converts a command described in a yaml document into a tuple describing the single command, its arguments, and its expected results.
	
	Parameters:
		yaml_cmds (dict): yaml doc specifying commands to run and report on.

	Returns:
		List of dicts
	"""
	map_required_args = {"description":"", "timeout":"", "returncode":"", "command":""}
	map_optional_args = {"expected":"success"}
	
	for key in map_required_args.keys():
		if key in yaml_cmds:
			map_required_args[key] = yaml_cmds[key]
		else:
			raise Exception(f"Parsing json failed. Missing required key: ({key})")

	for key in map_optional_args.keys():
		if key in yaml_cmds:
			map_optional_args[key] = yaml_cmds[key]

	#print("*** ", (map_required_args["description"], map_required_args["returncode"], map_required_args["timeout"], map_optional_args["expected"], cmd_tuple), " ***")
	return (map_required_args["description"], map_required_args["returncode"], map_required_args["timeout"], map_optional_args["expected"], map_required_args["command"])

def validate_timeout(timeout):
	"""
	Returns the positive timeout value. Timeout cannot be negative and is not capped.
	"""
	return max(timeout, -timeout)

def string_contains(text, substr, caseInsensitive=True):
	"""
	Returns True if text contains substr.

	Parameters:
		caseInsensitive (bool): True for case insensitive matching or False for case sensitive matching.

	Returns:
		bool: True if substr is found within text; False otherwise.
	"""
	s, subs = str(text), str(substr)
	if caseInsensitive:
		s, subs = s.lower(), subs.lower()
	return subs in s

def print_command_result_dict(results_dict):
	g_logger.info(f"\tCommand: '{results_dict['command']}'. Result: '{results_dict['result']}'. Message: '{results_dict['message']}'")

def get_command_result_dict(results_dict=None, result=None, command=None, message=None):
	if results_dict is None:
		results_dict = {"command":"", "result":"", "message":""}
	if result != None:
		results_dict["result"] = result
	if command != None:
		if isinstance(command, tuple):
			results_dict["command"] = " ".join(command)
		else:
			results_dict["command"] = command 
	if message != None:
		results_dict["message"] = message
	return results_dict

def get_junit_test_case_failed(descr, command, message):
	return f'\t\t<testcase name=" {descr}: {command} ">\n\t\t\t<failure message="{message} " type="WARNING"/>\n\t\t</testcase>\n'

def get_junit_test_case_succeeded(descr, command):
	return f'\t\t<testcase name=" {descr}: {command} "/>\n'

def execute_and_report(junit_output_xml_file, commands, logger=None, silent=False):
	"""
	Executes the list of commands and reports results.
	"""
	command_results = []
	command_results_junit = []
	failure_count = 0
	test_count = 0
	g_logger.info("Commands to test:")
	for c in commands:
		g_logger.info(f"\tComamnd: '{c}'")
		
	for descr, expected_command_code, timeout, expected, command in commands:
		command_text = " ".join(command)
		g_logger.info(f"Running command: '{command_text}'")
		cmd_code = 0
		command_results_dict = get_command_result_dict(None, command=command)
		msg = ""
		try:
			try:
				cmd_results = execmd(command, validate_timeout(timeout))
				cmd_code, cmd_stdout, cmd_stderr, cmd_timedout = cmd_results["returncode"], cmd_results["stdout"], cmd_results["stderr"], cmd_results["timedout"]
				if not silent:
					if not cmd_stdout.isspace():
						g_logger.info(f"stdout: {cmd_stdout}")
					if not cmd_stderr.isspace():
						g_logger.info(f"stderr: {cmd_stderr}")
				if string_contains(cmd_stderr, "not recogonized") and string_contains(cmd_stderr, f"'{command[0]}'"):
					raise Exception(cmd_stderr)
			except Exception as e:
				if expected == "failure" and not (string_contains(e, f"'{command[0]}'") and string_contains(e, "not recogonized")):
					g_logger.info(f"Command '{command_text}' ... Succeeded")
					command_results_dict = get_command_result_dict(command_results_dict, result="success")
				else:
					raise e
			if (cmd_timedout and expected == "timeout") or (expected == "success" and cmd_code == expected_command_code) or (expected == "failure" and cmd_code != expected_command_code):
				g_logger.info(f"Command '{command_text}' ... Succeeded")
				command_results_dict = get_command_result_dict(command_results_dict, result="success")
			else:
				cmd_err_report = ""
				if cmd_stderr != "":
					stderr_length = min(32, len(cmd_stderr))
					cmd_err = cmd_stderr.replace("\r\n", " ")[:stderr_length]
					if 32 < len(cmd_stderr):
						cmd_err = cmd_err + "..."
					cmd_err_report = f') and returned stderr: ({cmd_err}'
				g_logger.info(f"Command '{command_text}' ... Failed")
				if ((not cmd_timedout) and expected == "timeout"):
					msg = "Command Failed: command did not timeout"
				else:
					msg = f"Command Failed with return code: ({cmd_code}) different from expected return code: ({expected_command_code}{cmd_err_report})"
				command_results_dict = get_command_result_dict(command_results_dict, result="failure", message=msg)
				failure_count += 1
		except Exception as e:
			msg = "Command raise Exception: ({e})"
			g_logger.info(f"Command '{command_text}' ... Failed")
			command_results_dict = get_command_result_dict(command_results_dict, result="failure", message=msg)
			failure_count += 1
		if command_results_dict["result"] == "success":
			command_results_junit.append(get_junit_test_case_succeeded(descr, command_text))
		else:
			command_results_junit.append(get_junit_test_case_failed(descr, command_text, msg))
		command_results.append(command_results_dict)
		test_count += 1
		
	with open(junit_output_xml_file, "w") as junit_xml_file: 
		junit_xml_file.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
		junit_xml_file.write("<testsuites>\n")
		junit_xml_file.write(f'\t<testsuite id="0" name=" Commands to Test" tests="{test_count}" failures="{failure_count}" errors="0">\n')
		for test_case in command_results_junit:
			junit_xml_file.write(test_case)
		junit_xml_file.write("\t</testsuite>\n")
		junit_xml_file.write("</testsuites>\n")
		g_logger.info(f"Tests Completed: {test_count}. Failures: {failure_count}")
		g_logger.info(f"See test results in: '{junit_output_xml_file}'")
	with open(junit_output_xml_file, "r") as junit_xml_file: 
		g_logger.info(f"Test Commands Results written to '{junit_output_xml_file}': \n{junit_xml_file.read()}")

	g_logger.info(f"Test Commands Results: ")
	for results_dict in command_results:
		print_command_result_dict(results_dict)

def main(junit_output_xml_file, yaml_arg_cmds):
	# WORKS: python .\test_commands.py --commands="[{description: Test echo 1, returncode: 0, timeout: 2, command: echo, args: [hi, hi]}, {description: Test echo 2, returncode: 0, timeout: 1, expected: timeout, command: sleep, args: 2}]"
	yaml_cmds = yaml.safe_load(yaml_arg_cmds)
	commands_list = convert_all_yaml_cmds_into_cmds_list(yaml_cmds)
	g_logger.info(f"Writing JUnit xml results to '{junit_output_xml_file}'")
	execute_and_report(junit_output_xml_file, commands_list)
	g_logger.info("Tests Commands Completed")
	sys.exit(0)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='This script tests specified commands')
	parser.add_argument("-f", "--file", default="test_processes_results.xml", help="JUnit xml test results will be written to this file")
	parser.add_argument("-c", "--commands", default="", help="JSON list of commands to execute/test")
	args = parser.parse_args()
	main(args.file, args.commands)
