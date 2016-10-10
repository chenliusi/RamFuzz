// Copyright 2016 The RamFuzz contributors. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

namespace ns1 {
class A {
public:
  int sum = 0;
  void a() { sum += 100; }
  void b() { sum += 20; }
  void c() { sum += 3; }
};
}

namespace ns2 {
class A {
public:
  int sum = 0;
  void a() { sum += 1; }
  void a(int) { sum += 20; }
  void a(bool) { sum += 300; }
};
namespace ns2i {
class A {
public:
  int sum = 0;
  void a() { sum += 45; }
};
} // namespace ns2i
namespace {
class A {
public:
  int sum = 0;
  void a() { sum += 45; }
};
} // anonymous namespace
} // namespace ns2
