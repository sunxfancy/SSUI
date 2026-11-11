// Route axios consumers through the same offline transport as fetch consumers.
import axios from 'axios/unsafe/axios.js';
axios.defaults.adapter = 'fetch';
export default axios;
