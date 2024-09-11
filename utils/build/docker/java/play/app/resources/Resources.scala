package resources

import com.datadoghq.system_tests.iast.infra.SqlServer

class Resources {
  final val dataSource = new SqlServer().start
}
