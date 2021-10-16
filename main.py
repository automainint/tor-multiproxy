#!/usr/bin/python3

import os, shutil, time
import configparser
import argparse
import stem.process
from stem import Signal
from stem.control import Controller

def get_stop_file_name():
  return '.stop'

def get_ini_file_name():
  return 'tor-multiproxy.ini'

def parse_args(config_file):
  config = configparser.ConfigParser(
    defaults = { 'tor':          'tor/tor',
                 'count':        '4',
                 'switch_delay': '300',
                 'port_proxy':   '5100',
                 'port_control': '5200',
                 'exit_timeout': '5' })

  config.read(config_file)
  
  cfg = config['DEFAULT']

  parser = argparse.ArgumentParser(
    prog        = 'tor-multiproxy',
    description = 'Run multiple Tor proxies.'
  )

  parser.add_argument(
    '--stop',
    help    = 'stop running instance',
    dest    = 'stop',
    action  = 'store_const',
    const   = True,
    default = False
  )

  parser.add_argument(
    '--tor',
    type    = str,
    metavar = 'PATH',
    default = cfg.get('tor'),
    help    = 'path to tor executable',
    dest    = 'tor',
  )

  parser.add_argument(
    '--count',
    type    = int,
    metavar = 'INT',
    default = cfg.get('count'),
    help    = 'tor instance count',
    dest    = 'count',
  )

  parser.add_argument(
    '--switch_delay',
    type    = int,
    metavar = 'TIME',
    default = cfg.get('switch_delay'),
    help    = 'tor node switch delay in seconds',
    dest    = 'switch_delay',
  )

  parser.add_argument(
    '--port_proxy',
    type    = int,
    metavar = 'PORT',
    default = cfg.get('port_proxy'),
    help    = 'first tor proxy port',
    dest    = 'port_proxy',
  )

  parser.add_argument(
    '--port_control',
    type    = int,
    metavar = 'PORT',
    default = cfg.get('port_control'),
    help    = 'first tor control port',
    dest    = 'port_control',
  )

  parser.add_argument(
    '--proxies',
    type    = str,
    metavar = 'FILE',
    default = cfg.get('list'),
    help    = 'first tor control port',
    dest    = 'list',
  )

  parser.add_argument(
    '--exit_timeout',
    type    = int,
    metavar = 'TIME',
    default = cfg.get('exit_timeout'),
    help    = 'exit timeout in seconds',
    dest    = 'exit_timeout',
  )

  return parser.parse_args()

def print_log(text: str):
  print(text)

def run_proxy(tor: str, dir: str, port_proxy: int, port_control: int):
  print_log('Run Tor proxy on port ' + str(port_proxy) + '.')

  return stem.process.launch_tor_with_config(
    config = {
      'DataDirectory': dir,
      'SocksPort': str(port_proxy),
      'ControlPort': str(port_control)
    },
    tor_cmd = tor,
    take_ownership = True
  )

def new_tor_dir(n: int):
  dir = '.tor-' + str(n)
  if os.path.exists(dir):
    shutil.rmtree(dir)
  return dir

def free_dirs(count: int):
  for n in range(count):
    new_tor_dir(n)

def run_proxies(tor: str, count: int, port_proxy: int, port_control: int):
  pros = []
  for n in range(count):
    pros.append(
      run_proxy(
        tor, new_tor_dir(n),
        port_proxy + n,
        port_control + n))
  return pros

def do_stop():
  with open('.stop', 'w'): pass
  raise SystemExit

def is_done():
  return os.path.exists(get_stop_file_name())

def free_stop_file():
  if is_done():
    os.remove(get_stop_file_name())

def switch_node(port_proxy: int, port_control: int):
  con = Controller.from_port(port = port_control)
  con.authenticate()
  if con.is_newnym_available():
    print_log('Switch node for proxy on port ' + str(port_proxy) + '.')
    con.signal(Signal.NEWNYM)
  con.close()

def switch_nodes(port_proxy: int, port_control: int, count: int):
  for n in range(count):
    switch_node(port_proxy + n, port_control + n)

def switch_node_loop(args):
  switch_time = 0

  while not is_done():
    if switch_time >= args.switch_delay:
      switch_nodes(
        args.port_proxy,
        args.port_control,
        args.count)

      switch_time -= args.switch_delay

    switch_time += 1
    time.sleep(1)

def attach(port_control: int):
  ctr = Controller.from_port(port = port_control)
  ctr.authenticate()
  return ctr

def attach_all(count: int, port_control: int):
  cons = []
  for n in range(count):
    cons.append(attach(port_control + n))
  return cons

def close_all(cons, timeout: int):
  for con in cons:
    con.close()
  time.sleep(timeout)

def writedown_list(file: str, count: int, port: int):
  out = open(file, 'w')
  for n in range(count):
    out.write('127.0.0.1:' + str(port + n) + '\n')

def main():
  args = parse_args(get_ini_file_name())

  if args.stop:
    do_stop()

  try:
    print_log('Tor command: ' + args.tor)

    pros = run_proxies(
      args.tor, args.count,
      args.port_proxy,
      args.port_control)

    cons = attach_all(
      args.count,
      args.port_control)

    if args.list:
      writedown_list(
        args.list,
        args.count,
        args.port_proxy)

    switch_node_loop(args)
    close_all(cons, args.exit_timeout)

  except Exception as e:
    print_log(str(e) + '\n')

  free_dirs(args.count)
  free_stop_file()
  print_log('Done.')

if __name__ == '__main__':
  main()
