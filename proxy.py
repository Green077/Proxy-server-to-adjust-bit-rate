#!/usr/bin/env python
import os,sys,thread,socket,time,re

# five system execution arguments
file_path = sys.argv[1]
alpha = float(sys.argv[2])
port_browser = int(sys.argv[3])
fake_ip = sys.argv[4]
server_ip = sys.argv[5]

# create a socket to listen to the port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', port_browser))
s.listen(50)
T_current = 0
bitrate = '10'

def replace_nolist(request):
	regex = re.compile('GET /vod/big_buck_bunny.f4m')
	request = regex.sub('GET /vod/big_buck_bunny_nolist.f4m',request)
	return request

def replace_Seg_Frag(request):
	n = re.findall('Seg\d+-Frag\d+', request)
	if n != []:
		nS = re.findall('\d+', n[0])
		regex1 = re.compile('\d+Seg\d+-Frag\d+')
		p = bitrate + 'Seg'+ nS[0]+'-'+'Frag'+ nS[1]
		request = regex1.sub(p, request)
	else:
		p = ''
	return request, p

def find_header(words):
	words_list = words.split('\r\n\r\n')
	return words_list

def cal_total_length(chunk_request):
	content_length_list = re.findall("Content-Length:(.*)", chunk_request)
	if content_length_list != []:
		# calculate the length of the header
		head_length_list = find_header(chunk_request)
		head_length = len(head_length_list[0])
		total_length = int(content_length_list[0]) + head_length + 4
		remain_length = total_length - len(chunk_request)
	return total_length, remain_length

def cal_throughput(total_length, ts, tf, alpha, T_current):
	T_new = total_length / (tf-ts)
	T_current = alpha * T_new + (1-alpha) * T_current
	return T_current, T_new

def bitrate_select(T_current):
	# skip parhsing the manifest file
	# select the suitable bitrate directly
	if (T_current / 1.5)*8 >= 1000 * 1000:
		bitrate = '1000'
	elif 500*1000 <= (T_current /1.5)*8 < 1000*1000:
		bitrate = '500'
	elif 100*1000 <= (T_current / 1.5)*8 < 500*1000:				
		bitrate = '100'
	elif 10*1000 <= (T_current / 1.5)*8 < 100*1000:
		bitrate = '10'
	else:
		print 'something weried happen'
	return bitrate

def write_file(ts, tf, T_new, p, file_path, T_current):
	time_now = str(time.time() - ts)
	duration = str(tf-ts)
	# convert the bytes/s to Kbits/s
	T_n = str(T_new)
	T_c = str(T_current)
	chunk_name = '/vod/' + p
	with open(file_path, "a") as f: 
		f.write(time_now + ' '+ duration + ' ' + T_n + ' ' + T_c + ' ' + bitrate + ' ' + server_ip + ' ' + chunk_name + '\n')

def new_thread(c, addr):
	global T_current
	global bitrate
	max_rec = 8192
	server_port = 8080
	# a loop to wait for new request
	while True:
		request = c.recv(1024)
		# record the request received time from browser
		ts = time.time()
		# modify the request for manifest file
		request = replace_nolist(request)
		# modify the request for video chunk
		request, p = replace_Seg_Frag(request)
		print '---------------------Request--------------------------------------'
		print 'Request from browser is' + request
		try:
			# create another socket to connect to the server
			s_forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s_forward.bind((fake_ip, 0))
			s_forward.connect((server_ip, server_port))
			s_forward.send(request)
			data = ''
			# forward the request from client
			chunk_request = s_forward.recv(max_rec)
			data = data + chunk_request
			# calculate the total length and the remain length of the response
			total_length, remain_length = cal_total_length(chunk_request)
			#set the receive buffer size to be the remain length if the remain length
			# is smaller than the original buffer size
			while remain_length > 0:
				if remain_length > max_rec:
					chunk_request = s_forward.recv(max_rec)
					remain_length -= len(chunk_request)
					data = data + chunk_request
				else:
					chunk_request = s_forward.recv(remain_length)
					remain_length -= len(chunk_request)
					data = data + chunk_request
			# record the ending time of receving chunk from server
			tf = time.time()
			print 'tf - ts', tf-ts
			# calculate the throughput
			T_current, T_new = cal_throughput(total_length, ts, tf, alpha, T_current)
			# select the bitrate according to throughput
			bitrate = bitrate_select(T_current)
			# write some variables to a file
			write_file(ts, tf, T_new, p, file_path, T_current)

			if len(chunk_request) > 0:
				# send response back to the client
				c.send(data)
			else:
				print 'NOTHING IN Response'
				break
			s_forward.close()
		except socket.error, (value, message):
			if s_forward:
				s_forward.close()
			if c:
				c.close()
			sys.exit(1)
	c.close()

# a loop to wait for a client to connect
while True:
	c, addr = s.accept()
	# create a new thread triggered by a new client
	thread.start_new_thread(new_thread, (c, addr))
s.close()



