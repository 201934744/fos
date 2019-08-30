#pragma once

#include <vector>
#include <string>

#include "fpga_rpc.pb.h"
#include "fpga_rpc.grpc.pb.h"

typedef std::map<std::string, uint32_t> paramlist;

// represents a job
struct Job {
  std::string accname;
  paramlist params;
};


class FPGARPCClient {
  std::unique_ptr<FPGARPC::Stub> stub_;
public:
  FPGARPCClient();
  FPGARPCClient(const std::string &address);

  // Takes a batch of jobs and sands them to the server
  bool Run(std::vector<Job> &jobs);
  int Alloc();
  void Free(int bufno);
};
