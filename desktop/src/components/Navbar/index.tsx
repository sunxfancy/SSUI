import {Icon, IconName} from "@blueprintjs/core";
import styles from './style.module.css'
import PropTypes from "prop-types";
import {update} from "tar";

export const Navbar = (props: {navIndex:number}) => {
    const { navIndex, updateNavIndex } = props

    const icons: IconName[] = ["git-repo", "package", "sort", "settings"]

    const handleClick = (e) => {
        updateNavIndex(Number(e.currentTarget.dataset.index))
    }

    return (
        <div className={styles.navbar}>
            {
                icons.map((icon: string, index: number) => {
                    return (
                        <div className={`${styles.nav} ${index === navIndex ? styles.active : ''}`} data-index={index} onClick={handleClick} key={index}>
                            <Icon icon={icon}></Icon>
                            {
                                index === 2 &&
                                <div className={styles.queueSum}>3</div>
                            }

                        </div>
                    )
                })
            }
        </div>
    )
}

Navbar.propTypes = {
    navIndex: PropTypes.number.isRequired,
    updateNavIndex: PropTypes.func
}
