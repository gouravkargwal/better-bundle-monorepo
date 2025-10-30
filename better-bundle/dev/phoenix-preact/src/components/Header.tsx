import type { FunctionalComponent } from "preact";

const Header: FunctionalComponent<{
  title: string;
}> = ({ title }) => {
  return <h4>{title}</h4>;
};

export default Header;
