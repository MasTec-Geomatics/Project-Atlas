import { Link } from "@tanstack/react-router";

import arrow from "@/assets/not-found/arrow.svg";
import astronaut from "@/assets/not-found/astronaut.png";
import earth from "@/assets/not-found/earth.png";

import classes from "./NotFound.module.css";

/**
 * Page shown for a URL with no page: 404 over space, with a link back to the homepage.
 */
export function NotFound() {
  return (
    <main className={classes.page}>
      <img className={classes.astronaut} src={astronaut} alt="" />
      <div className={classes.earth}>
        <img className={classes.earthImage} src={earth} alt="" />
      </div>

      <div className={classes.content}>
        <h1 className={classes.code}>404</h1>
        <h2 className={classes.title}>Are you lost ?</h2>
        <p className={classes.message}>try to reload this page or go back to the homepage</p>
      </div>

      <Link to="/" className={classes.homeLink}>
        <img className={classes.arrow} src={arrow} alt="" />
        homepage
      </Link>
    </main>
  );
}
