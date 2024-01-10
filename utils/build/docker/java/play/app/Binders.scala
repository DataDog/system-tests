import play.api.mvc.PathBindable

package object Binders {
  implicit def seqPathBindable(implicit stringBinder: PathBindable[String]): PathBindable[Seq[String]] = new PathBindable[Seq[String]] {
    override def bind(key: String, value: String): Either[String, Seq[String]] = Right(value.split("/").toSeq)
    override def unbind(key: String, values: Seq[String]): String = values.mkString("/")
  }
}
