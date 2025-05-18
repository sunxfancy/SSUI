import { Icon, IconName } from "@blueprintjs/core";
import styles from './style.module.css'
import PropTypes from "prop-types";
import ChangeLng from "../ChangeLng";

export const Navbar = (props: {
    navIndex: number,
    updateNavIndex: (index: number) => void,
    openSettings: () => void
}) => {
    const { navIndex, updateNavIndex, openSettings } = props

    const icons: IconName[] = ["git-repo", "package", "sort", "settings"]

    const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
        updateNavIndex(Number(e.currentTarget.dataset.index))
    }

    return (
        <div className={styles.navbar}>
            {
                icons.map((icon: IconName, index: number) => {
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
            <ChangeLng />

            <div className={styles.settings} onClick={openSettings} key='settings'>
                <Icon icon="cog" />
            </div>
        </div>
    )
}

Navbar.propTypes = {
    navIndex: PropTypes.number.isRequired,
    updateNavIndex: PropTypes.func
}
